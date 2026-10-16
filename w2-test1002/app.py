from flask import Flask, render_template, request

app = Flask(__name__)

QUESTIONS = {
    "輸入輸出": {
        "text": "Python 中，哪個函式可以顯示文字在畫面上？",
        "options": [("A", "input()"), ("B", "print()"), ("C", "len()"), ("D", "int()")],
        "answer": "B",
    },
    "條件判斷": {
        "text": "Python 中，哪個關鍵字用來判斷條件是否成立？",
        "options": [("A", "for"), ("B", "def"), ("C", "if"), ("D", "import")],
        "answer": "C",
    },
    "迴圈": {
        "text": "想讓程式重複執行五次，通常可以使用哪個關鍵字？",
        "options": [("A", "for"), ("B", "return"), ("C", "class"), ("D", "break")],
        "answer": "A",
    },
    "串列": {
        "text": "Python 中，哪個寫法可以建立串列？",
        "options": [("A", "(1, 2, 3)"), ("B", "{1, 2, 3}"), ("C", "'1, 2, 3'"), ("D", "[1, 2, 3]")],
        "answer": "D",
    },
}


@app.route("/", methods=["GET", "POST"])
def home():
    selected_category = request.form.get("category") if request.method == "POST" else None
    question = QUESTIONS.get(selected_category)
    selected_answer = None
    result = None

    if request.method == "POST" and request.form.get("action") == "answer" and question:
        selected_answer = request.form.get("answer")
        valid_answers = {key for key, _ in question["options"]}
        if selected_answer in valid_answers:
            result = "correct" if selected_answer == question["answer"] else "incorrect"
        else:
            result = "missing"

    return render_template(
        "index.html",
        categories=QUESTIONS.keys(),
        selected_category=selected_category,
        question=question,
        selected_answer=selected_answer,
        result=result,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
