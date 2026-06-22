import os

from run import app


application = app


if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
