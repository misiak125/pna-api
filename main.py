import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, or_, func, desc
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime


""" ---------------------- DB configuration ------------------------- """
load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL not in .env")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
Base.metadata.create_all(bind=engine)


from models import Base, Product, Customer, Reservation, Brand, Model, Colour

SessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionMaker)

app = Flask(__name__)


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Automatic session closer"""
    db_session.remove()

def apply_search_filters(query, search_string: str, columns: list):
    """
    Edits query by adding a requirement for every word form 
    search_string to appear in any column.
    """
    if not search_string:
        return query
    
    words = search_string.strip().split()
    for word in words:
        search_term = f"%{word}%"
        or_conditions = [func.cast(col, String).ilike(search_term) for col in columns]
        query = query.filter(or_(*or_conditions))
    return query


"""------------------------------------------ GET ENDPOINS -----------------------------------------------"""

@app.route("/api/products/free", methods=["GET"])
def get_free_products():
    """ 
    Returns count of not reserved and not sold products from products table 
    groupped by brand, model, year and colour (also by expected delivery 
    depending on split_dates arg).
    Filters by showing only rows containing all words from search arg.
    Filters by year depending on show_year_free ("wszystkie" to show all)
    """
    search = request.args.get("search", "")
    split_dates = request.args.get("split_dates", "false").lower() == "true"
    show_year_free = request.args.get("show_year_free", "wszystkie")

    if not split_dates:
        query = db_session.query(
            Product.brand, Product.model, Product.year, Product.colour,
            func.max(Product.price).label("max_price"),
            func.count(Product.id).label("count"),
            func.min(Product.expected_delivery).label("delivery")
        ).outerjoin(Reservation).filter(
            Reservation.id == None, 
            Product.state != "Wydany"
        ).group_by(Product.brand, Product.model, Product.colour, Product.year)
    else:
        query = db_session.query(
            Product.brand, Product.model, Product.year, Product.colour,
            func.max(Product.price).label("max_price"),
            func.count(Product.id).label("count"),
            Product.expected_delivery.label("delivery")
        ).outerjoin(Reservation).filter(
            Reservation.id == None, 
            Product.state != "Wydany"
        ).group_by(Product.brand, Product.model, Product.colour, Product.year, Product.expected_delivery)

    if show_year_free != "wszystkie":
        try:
            query = query.filter(Product.year == int(show_year_free))
        except ValueError:
            pass

    columns_to_search = [
        Product.brand, Product.model, Product.year, 
        Product.colour, Product.expected_delivery
    ]
    query = apply_search_filters(query, search, columns_to_search)
    query = query.order_by(func.lower(Product.brand), func.lower(Product.model), Product.year)
    
    results = query.all()
    
    output = []
    for r in results:
        output.append({
            "brand": r.brand, "model": r.model, "year": r.year, 
            "colour": r.colour, "count": r.count, 
            "delivery": r.delivery.strftime('%d.%m.%Y') if r.delivery else "",
            "price": r.max_price
        })
    return jsonify(output)


@app.route("/api/products", methods=["GET"])
def get_all_products():
    """
    Returns products from products table.
    Filters by showing only rows containing all words from search arg.
    Filters by reserved / not reserved depending on show_reserved arg
    Filters by year depending on show_year_all arg. ('wszystkie' for all)
    Filters out products with 'wydany' state if show_sold == false
    """
    search = request.args.get("search", "")
    show_sold = request.args.get("show_sold", "false").lower() == "true"
    show_reserved = request.args.get("show_reserved", "wszystkie") # 'wszystkie', 'zarezerwowane', 'niezarezerwowane'
    show_year_all = request.args.get("show_year_all", "wszystkie")

    query = db_session.query(Product, Reservation).outerjoin(Reservation)

    if not show_sold:
        query = query.filter(Product.state != "Wydany")

    if show_year_all != "wszystkie":
        try:
            query = query.filter(Product.year == int(show_year_all))
        except ValueError:
            pass

    if show_reserved == "zarezerwowane":
        query = query.filter(Reservation.id.isnot(None))
    elif show_reserved == "niezarezerwowane":
        query = query.filter(Reservation.id.is_(None))

    columns_to_search = [
        Product.brand, Product.model, Product.year, Product.colour, 
        Product.order_id, Product.expected_delivery, Product.state
    ]
    query = apply_search_filters(query, search, columns_to_search)
    
    query = query.order_by(desc(Product.id))

    results = query.all()

    output = []
    for prod, res in results:
        is_reserved = "TAK" if res else "NIE"
        output.append({
            "id": prod.id,
            "brand": prod.brand,
            "model": prod.model,
            "year": prod.year,
            "colour": prod.colour,
            "price": prod.price,
            "state": prod.state,
            "added_on": prod.added_on.strftime("%d-%m-%Y %H:%M") if prod.added_on else "",
            "is_reserved": is_reserved,
            "delivery": prod.expected_delivery.strftime('%d.%m.%Y') if prod.expected_delivery else "",
            "order_id": prod.order_id
        })
    return jsonify(output)


@app.route("/api/customers", methods=["GET"])
def get_customers():
    """
    Returns customers from customers table.
    Filters by showing only rows containing all words from search arg.
    """
    search = request.args.get("search", "")
    query = db_session.query(Customer).order_by(desc(Customer.id))

    columns_to_search = [
        Customer.id, Customer.name, Customer.phone, Customer.email, 
        Customer.pesel, Customer.adress, Customer.company_name, Customer.nip
    ]
    query = apply_search_filters(query, search, columns_to_search)

    results = query.all()
    
    return jsonify([{
        "id": c.id, "name": c.name, "phone": c.phone, "email": c.email,
        "pesel": c.pesel, "nip": c.nip, "company_name": c.company_name,
        "adress": c.adress, "added_on": c.added_on.strftime("%d-%m-%Y %H:%M") if c.added_on else ""
    } for c in results])


@app.route("/api/reservations", methods=["GET"])
def get_reservations():
    """
    Returns reservations from reservations table.
    Filters by showing only rows containing all words from search arg.
    If show_finalized arg is false, hides reservations connected to 
    products of "wydany" state.
    """
    search = request.args.get("search", "")
    show_finalized = request.args.get("show_finalized", "false").lower() == "true"

    query = db_session.query(Reservation, Product, Customer)\
              .join(Product)\
              .join(Customer)

    if not show_finalized:
        query = query.filter(Product.state != "Wydany")

    columns_to_search = [
        Reservation.id, Customer.name, Reservation.date,
        Product.brand, Product.model, Product.colour, Reservation.adnotation
    ]
    query = apply_search_filters(query, search, columns_to_search)
    query = query.order_by(desc(Reservation.date))

    results = query.all()
    
    output = []
    for res, prod, cust in results:
        adnotation = res.adnotation or ""
        adnotation_short = adnotation[:36] + "..." if len(adnotation) > 36 else adnotation[:36]
        
        output.append({
            "reservation_id": res.id,
            "order_id": res.string_order_id,
            "customer_name": cust.name,
            "date": res.date.strftime("%d-%m-%Y %H:%M") if res.date else "",
            "brand": prod.brand,
            "model": prod.model,
            "colour": prod.colour,
            "adnotation": adnotation_short,
            "paid": res.paid
        })
    return jsonify(output)


@app.route("/api/colours", methods=["GET"])
def get_colours():
    """
    Returns all colours from colours table.
    """
    colours = db_session.query(Colour).order_by(Colour.name).all()
    return jsonify([c.name for c in colours])


@app.route("/api/brands", methods=["GET"])
def get_brands():
    """
    Returns all brands from brands table.
    """
    brands = db_session.query(Brand).order_by(Brand.name).all()
    return jsonify([b.name for b in brands])


@app.route("/api/models", methods=["GET"])
def get_models():
    """
    Returns all models form models table
    linked to brand (brand arg).
    """
    brand_name = request.args.get("brand")
    if not brand_name:
        return jsonify([])
    
    brand = db_session.query(Brand).filter(Brand.name == brand_name).first()
    if not brand:
        return jsonify([])
        
    models = db_session.query(Model).filter(Model.brand_id == brand.id).order_by(Model.name).all()
    return jsonify([m.name for m in models])


@app.route("/api/customers/<int:customer_id>", methods=["GET"])
def get_customer(customer_id):
    """
    Returns a customer of customer_id from customers table.
    """
    customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return jsonify({"error", f"Klient o id {customer_id} nie isnieje"}), 404
    return jsonify({
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "added_on": customer.added_on,
            "pesel": customer.pesel,
            "nip": customer.nip,
            "adress": customer.adress,
            "company_name": customer.company_name
        })


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    """
    Returns a product of product_id from products table.
    """
    prod = db_session.query(Product).filter(Product.id == product_id).first()
    if not prod:
        return jsonify({"error": "Brak produktu"}), 404
        
    return jsonify({
        "id": prod.id, "brand": prod.brand, "model": prod.model, 
        "colour": prod.colour, "year": prod.year, "price": prod.price, 
        "old_price": prod.old_price, "state": prod.state, "order_id": prod.order_id,
        "expected_delivery": prod.expected_delivery.strftime('%Y-%m-%d') if prod.expected_delivery else None
    })


@app.route("/api/reservations/<int:reservation_id>", methods=["GET"])
def get_reservation(reservation_id):
    """
    Returns a reservation of reservation_id joined with 
    its customer and product from reservations table.
    """
    res_tuple = db_session.query(Reservation, Product, Customer)\
        .join(Product).join(Customer)\
        .filter(Reservation.id == reservation_id).first()
        
    if not res_tuple:
        return jsonify({"error": "Brak rezerwacji"}), 404
        
    res, prod, cust = res_tuple
    return jsonify({
        "reservation_id": res.id,
        "customer_id": cust.id,
        "product_id": prod.id,
        "advance": res.advance,
        "adnotation": res.adnotation,
        "adnotation_pub": res.adnotation_pub,
        "form": res.form,
        "paid": res.paid,
        "term": res.term,
        "delivery": res.delivery,
        "payment_method": res.payment_method,
        "string_order_id": res.string_order_id
    })
""" ---------------------------- POST/DELETE ENDPOINTS -------------------------------- """

@app.route("/api/customers", methods=["POST"])
def add_new_customer():
    """ 
    Adds new customer of arguments 
    given to customers table.
    """
    data = request.get_json()
    try:
        new_customer = Customer(
            name=data.get("name"), 
            phone=data.get("phone"), 
            email=data.get("email"), 
            pesel=data.get("pesel"), 
            nip=data.get("nip"), 
            company_name=data.get("company_name"), 
            adress=data.get("adress"), 
            added_on=datetime.now()
        )
        db_session.add(new_customer)
        db_session.commit()
        return jsonify({"id": new_customer.id, "message": "Klient dodany"}), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd dodawania klienta: {e}"}), 400


@app.route("/api/reservations", methods=["POST"])
def make_new_reservation():
    """
    Adds new reservation of given args to reservations table.
    Links the new reservation to a product in products table (product_id arg).
    """
    data = request.get_json()
    product_id = data.get("product_id")


    product = db_session.query(Product).filter(Product.id == product_id).first()
    if not product:
        return jsonify({"error": "Produkt nie istnieje"}), 404
        

    existing_reservation = db_session.query(Reservation).filter(Reservation.product_id == product_id).first()
    if existing_reservation:
        return jsonify({"error": "Ten produkt jest już zarezerwowany"}), 409

    try:
        new_reservation = Reservation(
            date=datetime.now(),
            customer_id=data.get("customer_id"),
            product_id=product_id,
            advance=data.get("advance"),
            adnotation=data.get("adnotation"),
            adnotation_pub=data.get("adnotation_pub", ""),
            form=data.get("form"),
            paid=data.get("paid"),
            term=data.get("term"),
            delivery=data.get("delivery"),
            payment_method=data.get("payment_method"),
            string_order_id=data.get("string_order_id")
        )
        db_session.add(new_reservation)
        db_session.commit()
        return jsonify({"message": "Rezerwacja zakończona sukcesem"}), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd tworzenia rezerwacji {e}"}), 400


@app.route("/api/colours", methods=["POST"])
def add_colour():
    """ 
    Adds new colour (name arg) to colours table.
    """
    data = request.get_json()
    try:
        new_colour = Colour(name=data.get("name"))
        db_session.add(new_colour)
        db_session.commit()
        return jsonify({"message": "Dodano kolor"}), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd dodawania koloru: {e}"}), 400


@app.route("/api/colours/<name>", methods=["DELETE"])
def drop_colour(name):
    """ 
    Drops colour (name arg) from colours table.
    """
    try:
        col = db_session.query(Colour).filter(Colour.name == name).first()
        if col:
            db_session.delete(col)
            db_session.commit()
            return jsonify({"message": "Usunięto kolor"}), 200
    
        return jsonify({"error": "Kolor nie istnieje."}), 404
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd usuwania koloru: {e}"}), 400


@app.route("/api/brands", methods=["POST"])
def add_brand():
    """
    Adds a brand name (name arg) to brands table.
    """
    data = request.get_json()
    try:
        new_brand = Brand(name=data.get("name"))
        db_session.add(new_brand)
        db_session.commit()
        return jsonify({"message": "Dodano markę"}), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd dodawania marki: {e}"}), 400

@app.route("/api/brands/<name>", methods=["DELETE"])
def drop_brand(name):
    """ 
    Drops brand (name arg) from brands table.
    """
    try:
        brand = db_session.query(Brand).filter(Brand.name == name).first()
        if brand:
            db_session.delete(brand)
            db_session.commit()
            return jsonify({"message": "Usunięto markę"}), 200
        
        return jsonify({"error": "Marka nie istnieje."}), 404
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd usuwania marki: {e}"}), 400


@app.route("/api/models", methods=["POST"])
def add_model():
    """
    Adds new model (model arg) with brand 
    name (brand arg) linked to it to moedls table.
    """
    data = request.get_json()
    brand_name = data.get("brand")
    model_name = data.get("model")
    try:
        brand = db_session.query(Brand).filter(Brand.name == brand_name).first()
        if not brand:
            return jsonify({"error": "Marka nie istnieje."}), 404
        new_model = Model(name=model_name, brand_id=brand.id, namehash=f"{brand.id}$^{model_name}")
        db_session.add(new_model)
        db_session.commit()
        return jsonify({"message": "Dodano model"}), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": "Błąd dodawania modelu: {e}"}), 400

@app.route("/api/models/", methods=["DELETE"])
def drop_model():
    """ 
    Drops model (model arg) with brand (brand arg) from models table.
    """
    data = request.get_json()
    brand_name = data.get("brand")
    model_name = data.get("model")
    try:
        brand = db_session.query(Brand).filter(Brand.name == brand_name).first()
        if not brand:
            return jsonify({"error": "Marka nie istnieje."}), 404
        model = db_session.query(Model).filter(Model.name == model_name).filter(Model.brand_id == brand.id).first()
        if model:
            db_session.delete(model)
            db_session.commit()
            return jsonify({"message": "Usunięto kolor"}), 200
        
        return jsonify({"message": "Nie ma takiego modelu"}), 404
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd usuwania koloru: {e}"}), 400


@app.route("/api/products/<int:product_id>", methods=["PUT"])
def edit_product(product_id):
    """ 
    Edits product of product_id arg with args given.
    """
    data = request.get_json()
    try:
        product = db_session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return jsonify({"error": "Ten produkt nie istnieje."}), 404

        product.brand = data.get("brand", product.brand)
        product.model = data.get("model", product.model)
        product.colour = data.get("colour", product.colour)
        product.price = data.get("price", product.price)
        product.old_price = data.get("old_price", product.old_price)
        product.year = data.get("year", product.year)
        product.order_id = data.get("order_id", product.order_id)
        product.state = data.get("state", product.state)
        
        
        exp_deliv = data.get("expected_delivery")
        if exp_deliv:
            product.expected_delivery = datetime.strptime(exp_deliv, "%Y-%m-%dT%H:%M:%S")
            
        db_session.commit()
        return jsonify({"message": "Zaktualizowano produkt"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def drop_product(product_id):
    """
    Drops product of product_id arg.
    """
    try:
        product = db_session.query(Product).filter(Product.id == product_id).first()
        db_session.delete(product)
        db_session.commit()
        return jsonify({"message": "Usunięto produkt"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd edytowania produktu: {e}"}), 400


@app.route("/api/reservations/<int:reservation_id>", methods=["PUT"])
def edit_reservation(reservation_id):
    """ 
    Edits reservation of reservation_id arg with args given.
    """
    data = request.get_json()
    try:
        res_tuple = db_session.query(Reservation, Product).join(Product).filter(Reservation.id == reservation_id).first()
        
        if not res_tuple:
            return jsonify({"error": "Ta rezerwacja nie istnieje"}), 404
            
        reservation, product = res_tuple
        
        product.price = data.get("price", product.price)
        reservation.adnotation = data.get("adnotation", reservation.adnotation)
        reservation.adnotation_pub = data.get("adnotation_pub", reservation.adnotation_pub)
        reservation.advance = data.get("advance", reservation.advance)
        reservation.form = data.get("form", reservation.form)
        reservation.paid = data.get("paid", reservation.paid)
        reservation.term = data.get("term", reservation.term)
        reservation.delivery = data.get("delivery", reservation.delivery)
        reservation.payment_method = data.get("payment_method", reservation.payment_method)

        db_session.commit()
        return jsonify({"message": "Zaktualizowano rezerwację"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": f"Błąd edycji rezerwacji: {e}"}), 400

@app.route("/api/reservations/<int:reservation_id>", methods=["DELETE"])
def drop_reservation(reservation_id):
    """
    Drops reservaion of reservation_id.
    """
    try:
        product = db_session.query(Product).join(Reservation).filter(Reservation.id == reservation_id).first()
        if product:
            product.price = product.old_price
            
        res = db_session.query(Reservation).filter(Reservation.id == reservation_id).first()
        if res:
            db_session.delete(res)
            
        db_session.commit()
        return jsonify({"message": "Usunięto rezerwację i przywrócono cenę"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 400


@app.route("/api/products/first_free", methods=["GET"])
def get_first_free_element():
    """
    Returns first not reserved and not sold product
    matching given args (brand, model, colour, year, delivery)
    from products table.
    If delivery is not given then search for a product with no delivery info.
    """
    brand_given = request.args.get("brand")
    model_given = request.args.get("model")
    colour_given = request.args.get("colour")
    year_given = request.args.get("year")
    delivery_given = request.args.get("delivery")
    
    if delivery_given: 
        delivery_given = datetime.strptime(delivery_given, "%d.%m.%Y")
    else: 
        delivery_given = None

    result = db_session.query(Product).outerjoin(Reservation).filter(
        Reservation.id == None, 
        Product.state == "Oczekujemy na dostawę",
        Product.brand == brand_given, 
        Product.model == model_given,
        Product.colour == colour_given, 
        Product.year == year_given, 
        Product.expected_delivery == delivery_given
    ).first()
    
    if result is None:
        result = db_session.query(Product).outerjoin(Reservation).filter(
            Reservation.id == None, 
            Product.state != "Wydany",
            Product.brand == brand_given, 
            Product.model == model_given,
            Product.colour == colour_given, 
            Product.year == year_given, 
            Product.expected_delivery == delivery_given
        ).first()

    if result:
        return jsonify({"id": result.id, "price": result.price})
    return jsonify({"error": "Brak wolnych pojazdów o tych parametrach"}), 404

@app.route("/api/reservations/next_id", methods=["GET"])
def get_new_order_id():
    """
    Returns a potential id for new order.
    """
    try:
        last_res = db_session.query(Reservation).order_by(desc(Reservation.id)).first()
        new_id = last_res.id + 1 if last_res else 1
        return jsonify({"next_id": new_id})
    except:
        return jsonify({"next_id": 1})

if __name__ == "__main__":
    app.run(debug=True)