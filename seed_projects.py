import pandas as pd
import models
from auth import get_password_hash
from database import SessionLocal, engine, Base
from config import SWOOLLER_PASSWORD
import argparse


def seed_projects(path):
    admin_team = models.Team(name="University of Sussex Pearl Bioinformatics Lab")
    swooller_user = models.User(
        email="skw24@sussex.ac.uk",
        name="Sarah Wooller",
        hashed_password=get_password_hash(SWOOLLER_PASSWORD)
    )
    swooller_user.teams.append(admin_team)
    projects = create_projects(path, swooller_user, admin_team)
    return [admin_team, swooller_user] + projects


def create_projects(path, user, team):
    def make_project(row):

        return models.Project(
            pid=row['Award Reference'],
            version = "1.0.0",
            projectGrantName = row["Title"],
            leadResearcher = row["PI"],
            leadResearchInstitute = row["Host Institution"],
            grantNumbers = row['Award Reference'],
            projectGrantStartDate = row['Start Date'],
            projectGrantEndDate = row['End Date'],
            projectGrantScope = row['Abstract'],
            metadata_blob = dict(row[[i for i in row.index if i not in ['Award Reference', "Title",
                                                                      "PI", "Host Institution",
                                                                      'Award Reference', 'Start Date',
                                                                      'End Date', 'Abstract', 'Abstract.1']]]),
            status   = "DRAFT",
            user = user,
            team  = team)

    def change_dates(value):
        return value.strftime('%Y-%m-%d') if hasattr(value, 'strftime') else value


    df = pd.read_excel(path).map(change_dates)
    return list(df.apply(make_project, axis=1))


def main():
    parser = argparse.ArgumentParser(
        prog='seed projects',
        description='Given the path to an excel file, this seeds the database with the projects contained in it',
    )
    parser.add_argument('path')
    args = parser.parse_args()
    db = SessionLocal()
    db.add_all(seed_projects(args.path))
    db.commit()

if __name__ == "__main__":
    main()