# E-Commerce AI Chatbot (Level 2 ML)

An AI-powered chatbot for an e-commerce platform that can answer product questions, recommend items, track orders, and handle FAQs. This version uses a lightweight ML intent classifier with TF-IDF + Logistic Regression and a content-based recommendation engine.

## Features
- Intent classification (greeting, product search, recommendations, order tracking, refund, FAQ)
- Product search with price filtering
- Content-based product recommendations (cosine similarity)
- Order tracking by ID
- Simple, clean frontend chat UI

## Tech Stack
- Backend: FastAPI (Python)
- ML/NLP: scikit-learn, TF-IDF, Logistic Regression
- Data: JSON files (products, orders, intents)
- Frontend: HTML/CSS/JS

## Project Structure
```
ecommerce-ai-chatbot/
├── backend/
│   ├── app.py
│   ├── model.py
│   ├── intents.json
│   ├── products.json
│   ├── orders.json
│   └── artifacts/
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── requirements.txt
└── README.md
```

## Run Locally
1. Install dependencies
```
pip install -r requirements.txt
```

2. Start the backend
```
uvicorn backend.app:app --reload
```

3. Open the frontend
Open `frontend/index.html` in a browser.

## Example Prompts
- "Show me running shoes under $100"
- "Recommend a camera for travel"
- "Track order 1234"
- "What is your return policy?"

## Notes
- The intent model auto-trains on first run and is saved to `backend/artifacts/intent_model.joblib`.
- You can add more products or intents by editing the JSON files.

## Future Improvements
- Add user accounts and persistent chat history
- RAG over a real product database
- Personalized recommendations
- Sentiment-aware responses
- Deployment on Render/Railway
