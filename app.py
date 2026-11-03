"""Local demo monitoring app. Serves a placeholder dashboard only."""

from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


if __name__ == "__main__":
    # Demo only: listen on localhost so the app is not exposed on the network.
    app.run(host="127.0.0.1", port=5000, debug=False)
