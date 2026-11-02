import os
import sys
from flask import request, jsonify
from sqlalchemy import func, desc
from datetime import datetime

from src.models import Product, Customer, Reservation, Brand, Model, Colour, AppState
from src import app, limiter, db_session

from src.utils import (
    require_apikey,
    db_commit_update,
    apply_search_filters,
    log_creation,
    log_modification,
    update_and_log,
)
from src.pdf_generator import generate_pdf_confirmation

sys.path.insert(0, os.path.dirname(__file__))


""" ------------------------------------------ GET ENDPOINTS ----------------------------------------------- """

@app.route("/api/sync-status", methods=["GET"])
@limiter.exempt
@require_apikey
def get_sync_status():
    """
    Returns datetime of last change in database.
    """
    try:
        state = db_session.query(AppState).first()
        if not state:
            return jsonify({"last_update": "1970-01-01T00:00:00"}), 200
        return jsonify({"last_update": state.last_update.isoformat()}), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/products/free", methods=["GET"])
@require_apikey
def get_free_products():
    """ 
    Returns count of not reserved and not sold products from products table 
    grouped by brand, model, year and colour (also by expected delivery 
    depending on split_dates arg).
    Filters by showing only rows containing all words from search arg.
    Filters by year depending on show_year_free ("wszystkie" to show all)
    """
    try:
        search = request.args.get("search", "")
        split_dates = request.args.get("split_dates", "false").lower() == "true"
        show_year_free = request.args.get("show_year_free", "wszystkie")

        if not split_dates:
            query = db_session.query(
                func.min(Product.id).label("first_id"),
                Product.brand, Product.model, Product.year, Product.colour,
                func.max(Product.price).label("max_price"),
                func.count(Product.id).label("count"),
                func.min(Product.expected_delivery).label("delivery")
            ).outerjoin(Reservation).filter(
                Reservation.id.is_(None), 
                Product.state != "Wydany"
            ).group_by(Product.brand, Product.model, Product.colour, Product.year)
        else:
            query = db_session.query(
                func.min(Product.id).label("first_id"),
                Product.brand, Product.model, Product.year, Product.colour,
                func.max(Product.price).label("max_price"),
                func.count(Product.id).label("count"),
                Product.expected_delivery.label("delivery")
            ).outerjoin(Reservation).filter(
                Reservation.id.is_(None), 
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
                "first_free_id": r.first_id,
                "brand": r.brand, "model": r.model, "year": r.year, 
                "colour": r.colour, "count": r.count, 
                "delivery": r.delivery.strftime('%d.%m.%Y') if r.delivery else "",
                "price": r.max_price
            })
        return jsonify(output), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/products/all", methods=["GET"])
@require_apikey
def get_all_products():
    """
    Returns products from products table.
    Filters by showing only rows containing all words from search arg.
    Filters by reserved / not reserved depending on show_reserved arg
    Filters by year depending on show_year_all arg. ('wszystkie' for all)
    Filters out products with 'wydany' state if show_sold == false
    """
    try:
        search = request.args.get("search", "")
        show_sold = request.args.get("show_sold", "false").lower() == "true"
        show_reserved = request.args.get("show_reserved", "wszystkie")
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
        return jsonify(output), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/customers", methods=["GET"])
@require_apikey
def get_customers():
    """
    Returns customers from customers table.
    Filters by showing only rows containing all words from search arg.
    """
    try:
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
        } for c in results]), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/reservations", methods=["GET"])
@require_apikey
def get_reservations():
    """
    Returns reservations from reservations table.
    Filters by showing only rows containing all words from search arg.
    If show_finalized arg is false, hides reservations connected to 
    products of "wydany" state.
    """
    try:
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
        return jsonify(output), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/colours", methods=["GET"])
@require_apikey
def get_colours():
    """
    Returns all colours from colours table.
    """
    try:
        colours = db_session.query(Colour).order_by(Colour.name).all()
        return jsonify([c.name for c in colours]), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/brands", methods=["GET"])
@require_apikey
def get_brands():
    """
    Returns all brands from brands table.
    """
    try:
        brands = db_session.query(Brand).order_by(Brand.name).all()
        return jsonify([b.name for b in brands]), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/models", methods=["GET"])
@require_apikey
def get_models():
    """
    Returns all models form models table
    linked to brand (brand arg).
    """
    try:
        brand_name = request.args.get("brand")
        if not brand_name:
            return jsonify([]), 200
        
        brand = db_session.query(Brand).filter(Brand.name == brand_name.upper()).first()
        if not brand:
            return jsonify([]), 200
            
        models = db_session.query(Model).filter(Model.brand_id == brand.id).order_by(Model.name).all()
        return jsonify([m.name for m in models]), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/models/count", methods=["GET"])
@require_apikey
def get_models_count():
    try:
        brand_name = request.args.get("brand")
        if not brand_name:
            return jsonify({"count": 0}), 200
        
        brand = db_session.query(Brand).filter(Brand.name == brand_name.upper()).first()
        if not brand:
            return jsonify({"count": 0}), 200
            
        count = db_session.query(func.count(Model.id)).filter(Model.brand_id == brand.id).scalar() or 0
        return jsonify({"count": count}), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/customers/<int:customer_id>", methods=["GET"])
@require_apikey
def get_customer(customer_id):
    """
    Returns a customer of customer_id from customers table.
    """
    try:
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return jsonify({"error": f"Klient o id {customer_id} nie istnieje"}), 404
        return jsonify({
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "added_on": customer.added_on.strftime("%d-%m-%Y %H:%M") if customer.added_on else "",
            "pesel": customer.pesel,
            "nip": customer.nip,
            "adress": customer.adress,
            "company_name": customer.company_name,
        }), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/products/<int:product_id>", methods=["GET"])
@require_apikey
def get_product(product_id):
    """
    Returns a product of product_id from products table.
    """
    try:
        prod = db_session.query(Product).filter(Product.id == product_id).first()
        if not prod:
            return jsonify({"error": "Brak produktu"}), 404
            
        return jsonify({
            "id": prod.id, "brand": prod.brand, "model": prod.model, 
            "colour": prod.colour, "year": prod.year, "price": prod.price, 
            "old_price": prod.old_price, "state": prod.state, "order_id": prod.order_id,
            "expected_delivery": prod.expected_delivery.strftime('%Y-%m-%d') if prod.expected_delivery else None,
        }), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/reservations/<int:reservation_id>", methods=["GET"])
@require_apikey
def get_reservation(reservation_id):
    """
    Returns a reservation of reservation_id joined with 
    its customer and product from reservations table.
    """
    try:
        res_tuple = db_session.query(Reservation, Product, Customer)\
            .join(Product).join(Customer)\
            .filter(Reservation.id == reservation_id).first()
            
        if not res_tuple:
            return jsonify({"error": "Brak rezerwacji"}), 404
            
        res, prod, cust = res_tuple
        
        return jsonify({
            "reservation": {
                "id": res.id,
                "advance": res.advance,
                "adnotation": res.adnotation,
                "adnotation_pub": res.adnotation_pub,
                "form": res.form,
                "paid": res.paid,
                "term": res.term,
                "delivery": res.delivery,
                "payment_method": res.payment_method,
                "string_order_id": res.string_order_id,
                "date": res.date.strftime("%Y-%m-%dT%H:%M:%S") if res.date else None,
                "history": res.history or ""
            },
            "product": {
                "id": prod.id,
                "brand": prod.brand,
                "model": prod.model,
                "colour": prod.colour,
                "year": prod.year,
                "price": prod.price,
                "old_price": prod.old_price,
                "state": prod.state,
                "order_id": prod.order_id,
                "expected_delivery": prod.expected_delivery.strftime('%Y-%m-%d') if prod.expected_delivery else None,
                "history": prod.history or ""
            },
            "customer": {
                "id": cust.id,
                "name": cust.name,
                "phone": cust.phone,
                "email": cust.email,
                "pesel": cust.pesel,
                "nip": cust.nip,
                "company_name": cust.company_name,
                "adress": cust.adress,
                "history": cust.history or ""
            }
        }), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/reservations/last", methods=["GET"])
@require_apikey
def get_last_reservation():
    """
    Returns last reservation made.
    """
    try:
        res = db_session.query(Reservation).order_by(desc(Reservation.id)).first()
        if not res:
            return jsonify({"error": "Brak rezerwacji w bazie"}), 404
            
        return jsonify({
            "id": res.id,
            "string_order_id": res.string_order_id,
            "date": res.date.strftime("%d-%m-%Y %H:%M")
        }), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Wystąpił błąd serwera: {e}"}), 500


@app.route("/api/customers/<int:customer_id>/has_reservations", methods=["GET"])
@require_apikey
def do_customer_have_reservations(customer_id):
    """
    Returns information whether the customer of customer_id has any reservations made.
    """
    try:
        reservation = db_session.query(Reservation).filter(Reservation.customer_id == customer_id).first()
        if reservation:
            return jsonify({
                "is_reserved": True, 
                "reservation_id": reservation.id,
                "message": "Klient posiada rezerwacje."
            }), 200
        else:
            return jsonify({
                "is_reserved": False, 
                "message": "Klient nie ma rezerwacji."
            }), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Wystąpił błąd serwera: {e}"}), 400


@app.route("/api/products/<int:product_id>/is_reserved", methods=["GET"])
@require_apikey
def is_product_reserved(product_id):
    """
    Returns information whether the product of product_id is reserved.
    """
    try:
        reservation = db_session.query(Reservation).filter(Reservation.product_id == product_id).first()
        if reservation:
            return jsonify({
                "is_reserved": True, 
                "reservation_id": reservation.id,
                "message": "Produkt jest zarezerwowany."
            }), 200
        else:
            return jsonify({
                "is_reserved": False, 
                "message": "Produkt jest wolny."
            }), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Wystąpił błąd serwera: {e}"}), 400


@app.route("/api/products/first_free", methods=["GET"])
@require_apikey
def get_first_free_element():
    """
    Returns first not reserved and not sold product
    matching given args (brand, model, colour, year, delivery)
    from products table.
    If delivery is not given then search for a product with no delivery info.
    """
    try:
        brand_given = request.args.get("brand", "").upper()
        model_given = request.args.get("model", "").upper()
        colour_given = request.args.get("colour", "").upper()
        year_given = request.args.get("year")
        delivery_given = request.args.get("delivery")
        
        if delivery_given: 
            delivery_given = datetime.strptime(delivery_given, "%d.%m.%Y")
        else: 
            delivery_given = None

        result = db_session.query(Product).outerjoin(Reservation).filter(
            Reservation.id.is_(None), 
            Product.state == "Oczekujemy na dostawę",
            Product.brand == brand_given, 
            Product.model == model_given,
            Product.colour == colour_given, 
            Product.year == year_given, 
            Product.expected_delivery == delivery_given
        ).first()
        
        if result is None:
            result = db_session.query(Product).outerjoin(Reservation).filter(
                Reservation.id.is_(None), 
                Product.state != "Wydany",
                Product.brand == brand_given, 
                Product.model == model_given,
                Product.colour == colour_given, 
                Product.year == year_given, 
                Product.expected_delivery == delivery_given
            ).first()

        if result:
            return jsonify({"id": result.id, "price": result.price}), 200
        return jsonify({"error": "Brak wolnych pojazdów o tych parametrach"}), 404

    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/reservations/next_id", methods=["GET"])
@require_apikey
def get_new_order_id():
    """
    Returns a potential id for new order.
    """
    try:
        last_res = db_session.query(Reservation).order_by(desc(Reservation.id)).first()
        new_id = (last_res.id + 1) if last_res else 1
        return jsonify({"next_id": new_id}), 200
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/reservations/generate_pdf/<int:reservation_id>", methods=["GET"])
@require_apikey
def get_reservation_confirmation(reservation_id):
    try:
        filename = generate_pdf_confirmation(reservation_id)
        return jsonify({"message": "Utworzono pdf.", "directory": filename}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500


""" ---------------------------- POST / PUT / DELETE ENDPOINTS -------------------------------- """

@app.route("/api/products", methods=["POST"])
@require_apikey
def add_new_product():
    """ 
    Adds new product of arguments 
    given to products table.
    """

    data = request.get_json()
    username = getattr(request, 'current_user', 'system')
    
    try:
        exp_deliv_str = data.get("expected_delivery")
        exp_deliv_date = None
        if exp_deliv_str:
            if "T" in exp_deliv_str:
                exp_deliv_date = datetime.strptime(exp_deliv_str, "%Y-%m-%dT%H:%M:%S")
            else:
                exp_deliv_date = datetime.strptime(exp_deliv_str[:10], "%Y-%m-%d")

        price = data.get("price")

        new_product = Product(
            brand=str(data.get("brand", "")).upper(),
            model=str(data.get("model", "")).upper(),
            colour=str(data.get("colour", "")).upper(),
            year=data.get("year"),
            added_on=datetime.now(),
            price=price,
            old_price=price,
            order_id=data.get("order_id"),
            state="Oczekujemy na dostawę",
            expected_delivery=exp_deliv_date
        )
        log_creation(new_product, username)

        db_session.add(new_product)
        db_commit_update(db_session)

        return jsonify({
            "id": new_product.id, 
            "message": f"Produkt {new_product.brand} {new_product.model} dodany pomyślnie"
        }), 201

    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/customers", methods=["POST"])
@require_apikey
def add_new_customer():
    """ 
    Adds new customer of arguments 
    given to customers table.
    """
    data = request.get_json()
    username = getattr(request, 'current_user', 'system')
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
        log_creation(new_customer, username)

        db_session.add(new_customer)
        db_commit_update(db_session)
        return jsonify({"id": new_customer.id, "message": "Klient dodany"}), 201
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd dodawania klienta: {e}"}), 400


@app.route("/api/reservations", methods=["POST"])
@require_apikey
def make_new_reservation():
    """
    Adds new reservation of given args to reservations table.
    Links the new reservation to a product in products table (product_id arg).
    """
    data = request.get_json()
    username = getattr(request, 'current_user', 'system')
    product_id = data.get("product_id")

    product = db_session.query(Product).filter(Product.id == product_id).first()
    if not product:
        return jsonify({"error": "Produkt nie istnieje"}), 404

    existing_reservation = db_session.query(Reservation).filter(Reservation.product_id == product_id).first()
    if existing_reservation:
        return jsonify({"error": "Ten produkt jest już zarezerwowany"}), 409

    try:
        # Atomic price change if sent together with reservation creation
        new_price = data.get("price")
        if new_price is not None and str(new_price).strip() != "":
            try:
                new_price_val = float(new_price)
                if product.price != new_price_val:
                    log_modification(product, username, "price", product.price, new_price_val)
                    product.price = new_price_val
            except (ValueError, TypeError):
                pass

        # String order id auto-generation if not supplied
        string_order_id = data.get("string_order_id")
        if not string_order_id:
            last_res = db_session.query(Reservation).order_by(desc(Reservation.id)).first()
            current_year_suffix = str(int(datetime.now().year) % 100)
            if last_res and last_res.string_order_id and "/" in last_res.string_order_id:
                parts = last_res.string_order_id.split("/")
                if len(parts) == 2 and parts[1] == current_year_suffix:
                    try:
                        string_order_id = f"{int(parts[0]) + 1}/{current_year_suffix}"
                    except ValueError:
                        string_order_id = f"1/{current_year_suffix}"
                else:
                    string_order_id = f"1/{current_year_suffix}"
            else:
                string_order_id = f"1/{current_year_suffix}"

        new_reservation = Reservation(
            date=datetime.now(),
            customer_id=data.get("customer_id"),
            product_id=product_id,
            advance=data.get("advance") or 0.0,
            adnotation=data.get("adnotation", ""),
            adnotation_pub=data.get("adnotation_pub", ""),
            form=data.get("form"),
            paid=data.get("paid", False),
            term=data.get("term", ""),
            delivery=data.get("delivery", False),
            payment_method=data.get("payment_method", ""),
            string_order_id=string_order_id
        )
        log_creation(new_reservation, username)

        db_session.add(new_reservation)
        db_commit_update(db_session)
        return jsonify({
            "message": "Rezerwacja zakończona sukcesem",
            "reservation_id": new_reservation.id,
            "string_order_id": new_reservation.string_order_id
        }), 201
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd tworzenia rezerwacji: {e}"}), 400


@app.route("/api/colours", methods=["POST"])
@require_apikey
def add_colour():
    """ 
    Adds new colour (name arg) to colours table.
    """
    data = request.get_json()
    try:
        new_colour = Colour(name=str(data.get("name")).upper())
        db_session.add(new_colour)
        db_commit_update(db_session)
        return jsonify({"message": "Dodano kolor"}), 201
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd dodawania koloru: {e}"}), 400


@app.route("/api/colours/", methods=["DELETE"])
@require_apikey
@limiter.limit("5 per minute")
def drop_colour():
    """ 
    Drops colour (name arg from JSON) from colours table.
    """
    data = request.get_json()
    name = data.get("name", "")
    
    try:
        col = db_session.query(Colour).filter(Colour.name == name.upper()).first()
        if col:
            db_session.delete(col)
            db_commit_update(db_session)
            return jsonify({"message": "Usunięto kolor"}), 200
    
        return jsonify({"error": "Kolor nie istnieje."}), 404
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd usuwania koloru: {e}"}), 400


@app.route("/api/brands", methods=["POST"])
@require_apikey
def add_brand():
    """
    Adds a brand name (name arg) to brands table.
    """
    data = request.get_json()
    try:
        new_brand = Brand(name=str(data.get("name")).upper())
        db_session.add(new_brand)
        db_commit_update(db_session)
        return jsonify({"message": "Dodano markę"}), 201
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd dodawania marki: {e}"}), 400


@app.route("/api/brands/", methods=["DELETE"])
@require_apikey
@limiter.limit("5 per minute")
def drop_brand():
    """ 
    Drops brand and cascade deletes all its associated models on the server atomically.
    """
    data = request.get_json() or {}
    name = data.get("name", "")
    
    try:
        brand = db_session.query(Brand).filter(Brand.name == name.upper()).first()
        if brand:
            # Cascade delete associated models
            db_session.query(Model).filter(Model.brand_id == brand.id).delete(synchronize_session=False)
            db_session.delete(brand)
            db_commit_update(db_session)
            return jsonify({"message": "Usunięto markę i jej modele"}), 200
        
        return jsonify({"error": "Marka nie istnieje."}), 404
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd usuwania marki: {e}"}), 400


@app.route("/api/models", methods=["POST"])
@require_apikey
def add_model():
    """
    Adds new model (model arg) with brand 
    name (brand arg) linked to it to moedls table.
    """
    data = request.get_json()
    brand_name = str(data.get("brand")).upper()
    model_name = str(data.get("model")).upper()
    try:
        brand = db_session.query(Brand).filter(Brand.name == brand_name).first()
        if not brand:
            return jsonify({"error": "Marka nie istnieje."}), 404
        new_model = Model(name=model_name, brand_id=brand.id, namehash=f"{brand.id}$^{model_name}")
        db_session.add(new_model)
        db_commit_update(db_session)
        return jsonify({"message": "Dodano model"}), 201
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd dodawania modelu: {e}"}), 400


@app.route("/api/models/", methods=["DELETE"])
@require_apikey
@limiter.limit("5 per minute")
def drop_model():
    """ 
    Drops model (model arg) with brand (brand arg) from models table.
    """
    data = request.get_json()
    brand_name = data.get("brand", "").upper()
    model_name = data.get("model", "").upper()
    try:
        brand = db_session.query(Brand).filter(Brand.name == brand_name).first()
        if not brand:
            return jsonify({"error": "Marka nie istnieje."}), 404
        model = db_session.query(Model).filter(Model.name == model_name).filter(Model.brand_id == brand.id).first()
        if model:
            db_session.delete(model)
            db_commit_update(db_session)
            return jsonify({"message": "Usunięto model"}), 200
        
        return jsonify({"message": "Nie ma takiego modelu"}), 404
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd usuwania modelu: {e}"}), 400


@app.route("/api/products/<int:product_id>", methods=["PUT"])
@require_apikey
@limiter.limit("10 per minute")
def edit_product(product_id):
    """ 
    Edits product of product_id arg with args given.
    """
    data = request.get_json()
    username = getattr(request, 'current_user', 'system')
    try:
        product = db_session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return jsonify({"error": "Ten produkt nie istnieje."}), 404

        updates = {}
        if "brand" in data: updates["brand"] = str(data["brand"]).upper()
        if "model" in data: updates["model"] = str(data["model"]).upper()
        if "colour" in data: updates["colour"] = str(data["colour"]).upper()
        if "price" in data: updates["price"] = float(data["price"]) if data["price"] is not None else None
        if "old_price" in data: updates["old_price"] = float(data["old_price"]) if data["old_price"] is not None else None
        if "year" in data: updates["year"] = int(data["year"]) if data["year"] is not None else None
        if "order_id" in data: updates["order_id"] = data["order_id"]
        if "state" in data: updates["state"] = data["state"]
        
        if "expected_delivery" in data:
            raw_del = data["expected_delivery"]
            if raw_del:
                if "T" in raw_del:
                    updates["expected_delivery"] = datetime.strptime(raw_del, "%Y-%m-%dT%H:%M:%S")
                else:
                    updates["expected_delivery"] = datetime.strptime(raw_del[:10], "%Y-%m-%d")
            else:
                updates["expected_delivery"] = None

        update_and_log(product, updates, username)
            
        db_commit_update(db_session)
        return jsonify({"message": "Zaktualizowano produkt"}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/products/batch/date", methods=["PUT"])
@require_apikey
@limiter.limit("10 per minute")
def batch_update_product_date():
    """
    Updates expected_delivery for multiple products in a single atomic request.
    """
    data = request.get_json() or {}
    username = getattr(request, 'current_user', 'system')
    product_ids = data.get("ids", [])
    raw_date = data.get("expected_delivery")
    
    new_date = None
    if raw_date:
        try:
            if "T" in raw_date:
                new_date = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S")
            else:
                new_date = datetime.strptime(raw_date[:10], "%Y-%m-%d")
        except Exception:
            new_date = None

    try:
        products = db_session.query(Product).filter(Product.id.in_(product_ids)).all()
        for prod in products:
            if prod.expected_delivery != new_date:
                log_modification(prod, username, "expected_delivery", prod.expected_delivery, new_date)
                prod.expected_delivery = new_date

        db_commit_update(db_session)
        return jsonify({"message": f"Pomyślnie zaktualizowano datę dla {len(products)} pojazdów"}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
@require_apikey
@limiter.limit("60 per minute")
def drop_product(product_id):
    try:
        product = db_session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return jsonify({"error": "Produkt nie istnieje."}), 404
        db_session.delete(product)
        db_commit_update(db_session)
        return jsonify({"message": "Usunięto produkt"}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd usuwania produktu: {e}"}), 400


@app.route("/api/reservations/<int:reservation_id>", methods=["PUT"])
@require_apikey
@limiter.limit("10 per minute")
def edit_reservation(reservation_id):
    """ 
    Edits reservation of reservation_id arg with args given.
    """
    data = request.get_json()
    username = getattr(request, 'current_user', 'system')
    try:
        res_tuple = db_session.query(Reservation, Product).join(Product).filter(Reservation.id == reservation_id).first()
        if not res_tuple:
            return jsonify({"error": "Ta rezerwacja nie istnieje"}), 404
            
        reservation, product = res_tuple

        # Update product price if passed
        if "price" in data and data["price"] is not None and data["price"] != "":
            try:
                new_p = float(data["price"])
                if product.price != new_p:
                    log_modification(product, username, "price", product.price, new_p)
                    product.price = new_p
            except (ValueError, TypeError):
                pass

        res_updates = {}
        if "adnotation" in data: res_updates["adnotation"] = data["adnotation"]
        if "adnotation_pub" in data: res_updates["adnotation_pub"] = data["adnotation_pub"]
        if "advance" in data: res_updates["advance"] = float(data["advance"]) if data["advance"] is not None else 0.0
        if "form" in data: res_updates["form"] = data["form"]
        if "paid" in data: res_updates["paid"] = data["paid"]
        if "term" in data: res_updates["term"] = data["term"]
        if "delivery" in data: res_updates["delivery"] = data["delivery"]
        if "payment_method" in data: res_updates["payment_method"] = data["payment_method"]

        update_and_log(reservation, res_updates, username)

        db_commit_update(db_session)
        return jsonify({"message": "Zaktualizowano rezerwację"}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": f"Błąd edycji rezerwacji: {e}"}), 400


@app.route("/api/reservations/<int:reservation_id>", methods=["DELETE"])
@require_apikey
@limiter.limit("60 per minute")
def drop_reservation(reservation_id):
    username = getattr(request, 'current_user', 'system')
    """
    Drops reservaion of reservation_id.
    """
    try:
        product = db_session.query(Product).join(Reservation).filter(Reservation.id == reservation_id).first()
        if product:
            if product.old_price is not None and product.price != product.old_price:
                log_modification(product, username, "price", product.price, product.old_price)
                product.price = product.old_price
            
        res = db_session.query(Reservation).filter(Reservation.id == reservation_id).first()
        if res:
            db_session.delete(res)
            
        db_commit_update(db_session)
        return jsonify({"message": "Usunięto rezerwację i przywrócono cenę"}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/customers/<int:customer_id>", methods=["PUT"])
@require_apikey
@limiter.limit("10 per minute")
def edit_customer(customer_id):
    """ 
    Edits customer of customer_id arg with args given.
    """
    data = request.get_json()
    username = getattr(request, 'current_user', 'system')
    try:
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return jsonify({"error": "Brak klienta"}), 404

        cust_updates = {}
        for field in ["name", "phone", "email", "pesel", "nip", "company_name", "adress"]:
            if field in data:
                cust_updates[field] = data[field]

        update_and_log(customer, cust_updates, username)

        db_commit_update(db_session)
        return jsonify({"message": "Zaktualizowano dane klienta"}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/customers/<int:customer_id>", methods=["DELETE"])
@require_apikey
@limiter.limit("4 per minute")
def drop_customer(customer_id):
    try:
        """
        Drops customer of customer_id

        note: it's worth using do_customer_have_reservations endpoint before using this one to 
        avoid foreign key error
        """
        customer = db_session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
             return jsonify({"error": "Brak klienta"}), 404
             
        db_session.delete(customer)
        db_commit_update(db_session)
        return jsonify({"message": "Usunięto klienta"}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 400


application = app

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=False)
