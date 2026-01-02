if (Test-Path venv\Scripts\Activate.ps1) {
    & venv\Scripts\Activate.ps1
}

pip install -r requirements.txt
python app.py
