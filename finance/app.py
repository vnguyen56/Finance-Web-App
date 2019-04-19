import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get user id
    userId = session["user_id"]
    # get all transactions by the user
    transactions = db.execute("SELECT user_id, symbol, SUM(shares) as shares FROM Transactions WHERE user_id=:userId GROUP BY symbol HAVING SUM(shares)>0", userId=userId)
    
    # get total value of shares
    if transactions == None:
        return apology("no transactions", 404)
    else:
        symbolTotals = []
        for x in range(len(transactions)):
            symbolTotals.append(lookup(transactions[x]["symbol"])["price"] * transactions[x]["shares"])
        
    
    # get user cash
    cash=db.execute("SELECT cash FROM users WHERE id=:userId", userId=userId)[0]["cash"]
    
    
    total = cash + sum(symbolTotals)
    #for r in range(len(transactions)):
    #    symbolPrice = lookup(transactions[r]["symbol"])["price"]
    #    total += symbolPrice
    
    portlist = zip(transactions, symbolTotals)
    
    return render_template("index.html", portfolio=portlist, cash=float("{0:.2f}".format(cash)), total=float("{0:.2f}".format(total)))

 
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    if request.method=="POST":
        
        symbol=request.form.get("symbol")
        shares=request.form.get("shares")
        quote=lookup(symbol)
        user=db.execute("SELECT * FROM users WHERE id=:userid", userid=session["user_id"])
        userCash = user[0]["cash"]
        price=float(shares)*quote["price"]
        
        # check if user inputted symbol
        if not symbol:
            return apology("must provide symbol", 403)
        # check if symbol exists
        elif not quote:
            return apology("symbol does not exist", 403)
        # check if user inputted shares
        elif not shares:
            return apology("must input shares to buy", 403)
        # check if user can afford shares
        elif userCash < price:
            return apology("cannot afford shares", 403)
        else:
            db.execute("INSERT INTO Transactions(user_id, symbol, shares, time, type, purchase_price) VALUES(:user_id, :symbol, :shares, datetime('now'), 'BUY', :pprice)", 
                            user_id=session["user_id"], symbol=symbol, shares=shares, pprice=quote["price"])
            db.execute("UPDATE users SET cash=:cash WHERE id=:user_id", cash = userCash-price, user_id=session["user_id"])
                            
        return redirect("/")
        
    else:
        return render_template("buy.html")

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    """ Add cash to account"""
    
    if request.method=="POST":
        cashAmount = request.form.get("cashAmount")
        
        if not cashAmount:
            return apology("Please input cash amount", 403)
        else:
            db.execute("INSERT INTO users('cash') WHERE id=:userId", userId=session["user_id"])
            return redirect("/")
        
    else:
        return render_template("addcash.html")

@app.route("/check", methods=["GET"])
def check(username):
    """Return true if username available, else false, in JSON format"""

    checked=False
    rows = db.execute("SELECT * FROM users WHERE users.username=:username", username=username)
    
    if len(rows)>=1:
        checked=True
        
    return jsonify(checked)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    userId=session["user_id"]
    
    history = db.execute("SELECT * FROM Transactions WHERE user_id=:userId", userId=userId)
    
    return render_template("history.html", transactions=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    if request.method=="POST":
        
        # Ensure user entered a symbol
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 403)
        else:
            quote = lookup(request.form.get("symbol"))
            if not quote:
                return apology("Symbol does not exist")
            else:
                name = quote["name"]
                price = quote["price"]
                symbol = quote["symbol"]
                return render_template("quoted.html", name=name, price=price, symbol=symbol)
        
    else:
        return render_template("quote.html")
    


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        
        # Ensure confirmed password was submitted
        elif not (request.form.get("confirmation") == request.form.get("password")):
            return apology("Passwords do not match!", 403)
        
        # create hash of password 
        hash = generate_password_hash(request.form.get("password"))
        
        # Insert new user
        db.execute("INSERT INTO users(username, hash) VALUES(:username, :hash)",
                          username=request.form.get("username"), hash=hash)
        
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        
        # Add cash to portfolio
        #db.execute("INSERT INTO Portfolio(user_id, Symbol, TOTAL) VALUES(:user_id, 'CASH' , 10000.00)", user_id=request.form.get("username"))
                          
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
    


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method=="POST":
        
        symbol=request.form.get("symbol")
        shares=request.form.get("shares")
        quote=lookup(symbol)
        user=db.execute("SELECT * FROM users WHERE id=:userid", userid=session["user_id"])
        userCash = user[0]["cash"]
        price=float(shares)*quote["price"]
        userTrans=db.execute("SELECT shares FROM Transactions WHERE user_id=:userId AND symbol=:symbol GROUP BY symbol",userId=session["user_id"], symbol=symbol)
        if len(userTrans)==0:
            userShares=0
        else:
            userShares=userTrans[0]["shares"]
        
        # check if user inputted symbol
        if not symbol:
            return apology("must provide symbol", 403)
        # check if symbol exists
        elif not quote:
            return apology("symbol does not exist", 403)
        # check if user inputted shares
        elif not shares:
            return apology("must input shares to buy", 403)
        # check if user can sell shares
        elif int(userShares) < int(shares):
            return apology("do not have enough shares to sell", 403)
        else:
            db.execute("INSERT INTO Transactions(user_id, symbol, shares, time, type, purchase_price) VALUES(:user_id, :symbol, :shares, datetime('now'), 'SELL', :pprice)", 
                            user_id=session["user_id"], symbol=symbol, shares= -int(shares), pprice=quote["price"])
            db.execute("UPDATE users SET cash=:cash WHERE id=:user_id", cash = userCash+price, user_id=session["user_id"])
                            
        return redirect("/")
        
    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
