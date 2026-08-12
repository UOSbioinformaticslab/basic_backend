import requests

url = "http://localhost:8000/token"
data = {
    "username": "woollersarah@gmail.co.uk",
    "password": "password" # we don't know the password, but wait! We can just query the DB directly.
}
