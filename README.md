# Financial-Chatbot

## 📦 Requirements
- Python 3.10
- SEC API Key
- Amazon Bedrock (Anthropic) Access

## 🔐 API Keys Setup

1. **SEC API Key**  
   Sign up at [sec-api.io/signup/free](https://sec-api.io/signup/free) and get your free API key.

2. **Amazon Bedrock (Anthropic)**  
   Ensure you have access to Amazon Bedrock and credentials to use Anthropic models (e.g., Claude).

## ⚙️ Installation

Clone the repo and install dependencies:

```bash
git clone https://github.com/your-username/your-repo.git
cd Financial-Chatbot
pip install -r requirements.txt
cd Scripts
python main.py
```

**Custom Queries**
    Open main.py and update the questions list with any questions you'd like to ask. The system is designed to handle any queries related to the three companies within the specified timestamp range.