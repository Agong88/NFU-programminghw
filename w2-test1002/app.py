import json
import os
import time

from dotenv import load_dotenv
from flask import Flask, render_template, request, session
from google import genai
from google.genai import errors

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY') or os.urandom(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
CATEGORIES = ('輸入輸出', '條件判斷', '迴圈', '串列')
questions = {}
QUESTION_TTL = 3600
DEFAULT_MODEL = 'gemini-3.1-flash-lite'

QUESTION_PROMPT = '''你是 Python 入門老師，請依指定主題產生一題全新的 Python 3 單選題。
使用繁體中文，適合初學者。四個選項只能有一個正確答案，不需加 A、B、C、D 前綴。
程式碼使用換行與縮排，不要使用 Markdown 圍欄或 HTML。有 input() 時必須交代輸入值。
text 是題幹，options 是四個選項，answer 是 A、B、C、D 其中一個，explanation 是解題說明。
出題前請確認程式執行結果與答案一致。'''
QUESTION_SCHEMA = {
    'type': 'object',
    'properties': {
        'text': {'type': 'string'},
        'options': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 4, 'maxItems': 4},
        'answer': {'type': 'string', 'enum': list('ABCD')},
        'explanation': {'type': 'string'},
    },
    'required': ['text', 'options', 'answer', 'explanation'],
}


def generate_question(category):
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    if not api_key:
        raise ValueError('請先在 .env 設定 GEMINI_API_KEY，再重新啟動程式。')
    with genai.Client(api_key=api_key, http_options={'timeout': 60000, 'retry_options': {'attempts': 2}}) as client:
        response = client.models.generate_content(
            model=os.getenv('GEMINI_MODEL', '').strip() or DEFAULT_MODEL,
            contents=f'請產生一題關於「{category}」的 Python 入門單選題。',
            config={'system_instruction': QUESTION_PROMPT,
                    'response_mime_type': 'application/json',
                    'response_json_schema': QUESTION_SCHEMA},
        )
    try:
        question = json.loads(response.text or '')
        if not isinstance(question, dict):
            raise ValueError
        for field in ('text', 'explanation'):
            value = question.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 5000:
                raise ValueError
        options = question.get('options')
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError
        if any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in options):
            raise ValueError
        if len({v.strip() for v in options}) != 4 or question.get('answer') not in ('A', 'B', 'C', 'D'):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('AI 回傳的題目格式不完整，請重新出題。') from None
    question['options'] = list(zip('ABCD', options))
    return question


@app.route('/', methods=['GET', 'POST'])
def home():
    for key, value in list(questions.items()):
        if time.time() - value['created_at'] >= QUESTION_TTL:
            questions.pop(key, None)
    question_id = session.get('question_id')
    stored = questions.get(question_id)
    selected_category = stored['category'] if stored else None
    question = stored['question'] if stored else None
    selected_answer = result = error = None

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'generate':
            category = request.form.get('category')
            if category not in CATEGORIES:
                error = '請先選擇學習主題。'
            else:
                try:
                    new_question = generate_question(category)
                    questions.pop(question_id, None)
                    # 最多暫存 500 題，避免記憶體持續增加。
                    if len(questions) >= 500:
                        questions.pop(next(iter(questions)), None)
                    question_id = os.urandom(24).hex()
                    questions[question_id] = {
                        'category': category, 'question': new_question, 'created_at': time.time(),
                    }
                    session['question_id'] = question_id
                    selected_category, question = category, new_question
                except errors.APIError as exc:
                    if exc.code == 429:
                        error = 'API 額度已用完或請求過於頻繁，請稍後再試，或檢查 Gemini 配額。'
                    elif exc.code == 504:
                        error = 'Gemini 模型回應逾時（504），請稍後重試，或在 .env 將 GEMINI_MODEL 設為 gemini-3.1-flash-lite 後重啟程式。'
                    elif exc.code == 404:
                        error = 'Gemini 模型不存在或目前帳號無法使用，請檢查 .env 的 GEMINI_MODEL 設定。'
                    elif exc.code in (400, 401, 403):
                        error = '請檢查 Gemini API 金鑰、模型名稱及存取權限。'
                    else:
                        error = 'Gemini 服務暫時無法出題，請稍後再試。'
                except ValueError as exc:
                    error = str(exc)
                except Exception:
                    error = '出題失敗，請檢查網路連線後再試。'
        elif action == 'answer':
            if not question or request.form.get('question_id') != question_id:
                error = '題目已過期或已更新，請重新出題後作答。'
            else:
                selected_answer = request.form.get('answer')
                if selected_answer in ('A', 'B', 'C', 'D'):
                    result = 'correct' if selected_answer == question['answer'] else 'incorrect'
                else:
                    result = 'missing'
        else:
            error = '無效的操作，請重新選擇主題。'
    return render_template(
        'index.html', categories=CATEGORIES, selected_category=selected_category,
        question=question, question_id=question_id, selected_answer=selected_answer,
        result=result, error=error,
    )


if __name__ == '__main__':
    app.run(port=5000)
