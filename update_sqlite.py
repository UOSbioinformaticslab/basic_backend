import sys
import json
import shutil
import os
from sqlalchemy import create_engine, text
from database import Base
import models  # to ensure all models are registered
from datetime import datetime

def parse_datetime(val):
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            pass
    return val

def generate_description(name):
    specifics = {
        'University College London': 'A leading data custodian based at UCL, focused on curating comprehensive multimodal datasets spanning genomics, imaging, and clinical trials for oncology research.',
        'Institute of Cancer Research': 'The ICR data team manages an extensive portfolio of cancer datasets, with a particular emphasis on drug discovery, molecular pathology, and targeted therapies.',
        'Cancer Research Horizons': 'The innovation engine of CRUK, managing datasets derived from translational research and commercial partnerships to accelerate cancer breakthroughs.',
        'University of Cambridge': 'The Cambridge data custodian team curates high-impact datasets from the CRUK Cambridge Centre, encompassing early detection, functional genomics, and population studies.',
        'Cambridge University Hospitals NHS Trust': 'The Cambridge data custodian team curates high-impact datasets from the CRUK Cambridge Centre, encompassing early detection, functional genomics, and population studies.',
        'University of Oxford': "Oxford's data custodians provide access to world-class clinical and molecular datasets, specializing in immuno-oncology and precision medicine.",
        'Oxford University': "Oxford's data custodians provide access to world-class clinical and molecular datasets, specializing in immuno-oncology and precision medicine.",
        'The Francis Crick Institute': 'The Crick data team oversees cutting-edge biomedical datasets generated from advanced discovery science, including single-cell sequencing and structural biology.',
        "King's College London": 'KCL data custodians manage datasets spanning cancer epidemiology, palliative care, and comprehensive cancer imaging.',
        'Royal Marsden Hospital': 'As a leading specialist cancer hospital, the Royal Marsden team curates highly detailed longitudinal clinical datasets and real-world evidence.',
        'University of Birmingham': 'The Birmingham data team manages specialized datasets covering cancer immunology, clinical trials, and population health studies.',
        'University of Manchester': 'The Manchester data team curates translational datasets focusing on radiotherapy, biomarkers, and precision oncology.',
    }
    
    if name in specifics:
        return specifics[name]
    
    if 'University' in name or 'College' in name:
        return f"An academic data custodian based at {name}, dedicated to sharing high-quality, research-grade datasets to drive forward collaborative cancer research."
    elif 'Hospital' in name or 'Center' in name or 'Centre' in name or 'Clinic' in name or 'Trust' in name:
        return f"A clinical data custodian at {name}, providing access to rich clinical trial data, real-world evidence, and patient outcomes to support translational oncology."
    elif 'Institute' in name:
        return f"A specialized data custodian team at the {name}, curating foundational datasets in molecular biology and experimental cancer medicine."
    
    return f"A dedicated data custodian team at {name}, managing and providing access to valuable research datasets to support the global cancer research community."

def run():
    db_file = "cruk_datahub.db"
    backup_file = "cruk_datahub.db.backup"
    
    # 1. Create a backup
    print(f"Creating backup of {db_file} to {backup_file}...")
    shutil.copy2(db_file, backup_file)
    
    sqlite_backup_url = f"sqlite:///{backup_file}"
    sqlite_new_url = f"sqlite:///{db_file}"

    engine_old = create_engine(sqlite_backup_url)
    engine_new = create_engine(sqlite_new_url)

    # 2. Recreate schema in the new database file
    print("Recreating tables with the new schema in SQLite...")
    Base.metadata.drop_all(engine_new) # Drop all existing tables in cruk_datahub.db
    Base.metadata.create_all(engine_new) # Recreate them with updated models

    with engine_old.connect() as conn_old:
        with engine_new.begin() as conn_new:
            # 3. Fetch data that needs mapping
            print("Extracting datasets, projects, and users from backup...")
            datasets = [{k: parse_datetime(v) for k, v in dict(r._mapping).items()} for r in conn_old.execute(text("SELECT * FROM datasets")).fetchall()]
            projects = [{k: parse_datetime(v) for k, v in dict(r._mapping).items()} for r in conn_old.execute(text("SELECT * FROM projects")).fetchall()]
            users = [{k: parse_datetime(v) for k, v in dict(r._mapping).items()} for r in conn_old.execute(text("SELECT * FROM users")).fetchall()]
            
            # Find the user we want to link
            target_user_id = next((u['id'] for u in users if u['email'] == 'skw24@sussex.ac.uk'), None)

            teams_data = {}
            team_id_counter = 1
            
            # Extract from datasets first
            for ds in datasets:
                if ds['metadata_blob']:
                    try:
                        meta = json.loads(ds['metadata_blob'])
                        custodian = meta.get('summary', {}).get('dataCustodian', {})
                        name = custodian.get('name')
                        url = custodian.get('url')
                        
                        if name and name not in teams_data:
                            teams_data[name] = {
                                'id': team_id_counter,
                                'name': name,
                                'notification_email': 'woollersarah@gmail.com',
                                'hdr_gateway_email': None,
                                'description': generate_description(name),
                                'url': url
                            }
                            team_id_counter += 1
                        
                        # Map dataset to team
                        if name:
                            ds['team_id'] = teams_data[name]['id']
                        else:
                            ds['team_id'] = None
                    except Exception as e:
                        print(f"Error parsing metadata for dataset {ds['id']}: {e}")
                        ds['team_id'] = None
            
            # Extract from projects
            for proj in projects:
                name = proj['lead_research_institute']
                if name:
                    if name not in teams_data:
                        teams_data[name] = {
                            'id': team_id_counter,
                            'name': name,
                            'notification_email': 'woollersarah@gmail.com',
                            'hdr_gateway_email': None,
                            'description': generate_description(name),
                            'url': None
                        }
                        team_id_counter += 1
                    proj['team_id'] = teams_data[name]['id']
                else:
                    proj['team_id'] = None

            # 4. Map and copy data to new SQLite DB
            print("Mapping and copying data to new SQLite database...")
            for table in Base.metadata.sorted_tables:
                print(f"Copying {table.name}...")
                
                if table.name == 'teams':
                    dicts = list(teams_data.values())
                    if dicts:
                        conn_new.execute(table.insert(), dicts)
                
                elif table.name == 'user_teams':
                    if target_user_id:
                        dicts = [{'user_id': target_user_id, 'team_id': t['id'], 'is_team_admin': True} for t in teams_data.values()]
                        if dicts:
                            conn_new.execute(table.insert(), dicts)
                            
                elif table.name == 'datasets':
                    if datasets:
                        conn_new.execute(table.insert(), datasets)
                        
                elif table.name == 'projects':
                    if projects:
                        conn_new.execute(table.insert(), projects)
                        
                else:
                    rows = conn_old.execute(text(f"SELECT * FROM {table.name}")).fetchall()
                    if rows:
                        dicts = [{k: parse_datetime(v) for k, v in dict(row._mapping).items()} for row in rows]
                        conn_new.execute(table.insert(), dicts)
                        
            print("Successfully migrated data to cruk_datahub.db!")

if __name__ == "__main__":
    run()
