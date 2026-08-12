import sys
import json
from sqlalchemy import create_engine, text
from database import Base
import models  # to ensure all models are registered

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
    sqlite_url = "sqlite:///cruk_datahub.db"
    pg_url = "postgresql://postgres:hkJiqclpUJHSsJIhDSXiMGQFOtkDTmpX@monorail.proxy.rlwy.net:20854/railway"

    sqlite_engine = create_engine(sqlite_url)
    pg_engine = create_engine(pg_url)

    print("Creating tables in PostgreSQL...")
    Base.metadata.drop_all(pg_engine) # let's start fresh
    Base.metadata.create_all(pg_engine)

    with sqlite_engine.connect() as conn_lite:
        with pg_engine.begin() as conn_pg:
            # 1. Fetch data that needs mapping
            print("Extracting datasets, projects, and users...")
            datasets = [dict(r._mapping) for r in conn_lite.execute(text("SELECT * FROM datasets")).fetchall()]
            projects = [dict(r._mapping) for r in conn_lite.execute(text("SELECT * FROM projects")).fetchall()]
            users = [dict(r._mapping) for r in conn_lite.execute(text("SELECT * FROM users")).fetchall()]
            
            # Find the user we want to link
            target_user_id = next((u['id'] for u in users if u['email'] == 'skw24@sussex.ac.uk'), None)

            teams_data = {}
            team_id_counter = 1
            
            # Extract from datasets first (per user instructions)
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

            # 2. Copy tables in order to satisfy FK constraints
            # Tables to handle specially: teams, user_teams, datasets, projects
            print("Mapping and copying data to PostgreSQL...")
            for table in Base.metadata.sorted_tables:
                print(f"Copying {table.name}...")
                
                if table.name == 'teams':
                    dicts = list(teams_data.values())
                    if dicts:
                        conn_pg.execute(table.insert(), dicts)
                
                elif table.name == 'user_teams':
                    if target_user_id:
                        dicts = [{'user_id': target_user_id, 'team_id': t['id'], 'is_team_admin': True} for t in teams_data.values()]
                        if dicts:
                            conn_pg.execute(table.insert(), dicts)
                            
                elif table.name == 'datasets':
                    if datasets:
                        conn_pg.execute(table.insert(), datasets)
                        
                elif table.name == 'projects':
                    if projects:
                        conn_pg.execute(table.insert(), projects)
                        
                else:
                    rows = conn_lite.execute(text(f"SELECT * FROM {table.name}")).fetchall()
                    if rows:
                        dicts = [dict(row._mapping) for row in rows]
                        conn_pg.execute(table.insert(), dicts)
                
                # Reset sequence for PostgreSQL if it has an id column
                if 'id' in table.columns:
                    try:
                        reset_query = f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), COALESCE((SELECT MAX(id)+1 FROM {table.name}), 1), false)"
                        conn_pg.execute(text(reset_query))
                    except Exception as e:
                        print(f"Could not reset sequence for {table.name}: {e}")
                        
            print("Successfully migrated data to PostgreSQL!")

if __name__ == "__main__":
    run()
