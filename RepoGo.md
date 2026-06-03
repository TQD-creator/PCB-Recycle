#1
cd Mobile_app_deploy\backend
cd Mobile_app_deploy\frontend
#2
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
#The main .repo is at Mobile_app_deploy\frontend