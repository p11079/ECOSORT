# EcoSort AI — v1.0.0

Initial working MVP for the lightweight waste-segregation assistant.

Planned stack:

- Python
- Streamlit
- Gemini Vision API
- CSV or SQLite
- Plotly

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app works in demo mode without an API key. To enable Gemini Vision, add this to `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your-key"
```

Never commit `secrets.toml` to GitHub.
