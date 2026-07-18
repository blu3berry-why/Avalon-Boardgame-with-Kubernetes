
# 3.10, not 3.8: Django 4.0 uses stdlib zoneinfo on >=3.9; on 3.8 it pulls
# backports.zoneinfo, which has no arm64 wheel and needs gcc to compile.
FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "manage.py", "runserver", "0.0.0.0:8000" ]

