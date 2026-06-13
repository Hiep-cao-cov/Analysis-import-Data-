@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pip install -q streamlit plotly openpyxl
streamlit run app.py
