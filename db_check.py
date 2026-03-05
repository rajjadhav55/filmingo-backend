import os
import django
import sys

# Add the current directory to sys.path to find the settings module
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyshow.settings')
django.setup()

from django.db import connection

try:
    tables = connection.introspection.table_names()
    with open('db_check.txt', 'w') as f:
        f.write("Tables found:\n")
        f.write('\n'.join(tables))
    print("Check complete. See db_check.txt")
except Exception as e:
    with open('db_check.txt', 'w') as f:
        f.write(f"Error: {str(e)}")
    print(f"Error: {str(e)}")
