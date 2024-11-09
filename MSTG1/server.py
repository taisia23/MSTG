from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///motoshop.db'
db = SQLAlchemy(app)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    manufacturer = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer)
    stock = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(200))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True)
    contact = db.Column(db.String(20), nullable=False)
    is_manager = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(100)) 
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))  # Add this line
    birth_date = db.Column(db.Date)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True) 
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    phone = db.Column(db.String(20))


@app.route('/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id, 'name': p.name, 'category': p.category,
        'manufacturer': p.manufacturer, 'model': p.model,
        'year': p.year, 'stock': p.stock, 'price': p.price,
        'description': p.description, 'image_url': p.image_url
    } for p in products])

@app.route('/products', methods=['POST'])
def add_product():
    data = request.json
    new_product = Product(**data)
    db.session.add(new_product)
    db.session.commit()
    return jsonify({'message': 'Product added successfully'}), 201

@app.route('/managers/<int:telegram_id>', methods=['GET'])
def get_manager(telegram_id):
    manager = Manager.query.filter_by(telegram_id=telegram_id).first()
    if manager:
        return jsonify({
            'id': manager.id,
            'telegram_id': manager.telegram_id,
            'first_name': manager.first_name,
            'last_name': manager.last_name,
            'phone': manager.phone
        }), 200
    else:
        return jsonify({'error': 'Manager not found'}), 404

@app.route('/managers', methods=['POST'])
def create_manager():
    try:
        data = request.json
        new_manager = Manager(**data)
        db.session.add(new_manager)
        db.session.commit()
        return jsonify({'message': 'Manager created successfully'}), 201
    except IntegrityError as e:
        db.session.rollback()
        if 'UNIQUE constraint failed: manager.telegram_id' in str(e):
            return jsonify({'error': 'Manager with this telegram_id already exists'}), 409
        app.logger.error(f"Error creating manager with data {data}: {e}")
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating manager with data {data}: {e}")
        return jsonify({'error': 'An error occurred while creating the manager'}), 500

@app.route('/customers/<int:customer_id>', methods=['GET', 'PUT'])
def customer(customer_id):
    customer = Customer.query.filter_by(telegram_id=customer_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': customer.id,
            'telegram_id': customer.telegram_id,
            'contact': customer.contact,
            'is_manager': customer.is_manager,
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'phone': customer.phone,
            'birth_date': customer.birth_date.isoformat() if customer.birth_date else None
        }), 200

    elif request.method == 'PUT':
        data = request.get_json()
        for key, value in data.items():
            setattr(customer, key, value)
        db.session.commit()
        return jsonify({'message': 'Customer updated successfully'}), 200

@app.route('/customers', methods=['POST'])
def add_customer():
    data = request.json
    # Перевіряємо обов'язкові поля
    required_fields = ["telegram_id", "contact", "is_manager"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    new_customer = Customer(**data)
    db.session.add(new_customer)
    try:
        db.session.commit()
    except IntegrityError:  # Обробляємо помилку, якщо користувач уже існує
        db.session.rollback()
        return jsonify({"error": "Customer already exists"}), 409

    return jsonify({'message': 'Customer added successfully'}), 201

@app.route('/customers/check', methods=['GET'])
def check_customer_exists():
    telegram_id = request.args.get("telegram_id")
    contact = request.args.get("contact")

    customer = Customer.query.filter_by(telegram_id=telegram_id).first()
    if customer:
        return jsonify({"exists": True}), 200

    customer = Customer.query.filter_by(contact=contact).first()
    if customer:
        return jsonify({"exists": True}), 200

    return jsonify({"exists": False}), 200

@app.route('/orders', methods=['POST'])
def create_order():
    data = request.json
    new_order = Order(
        customer_id=data['customer_id'],
        total_price=data['total_price'],
        status='processing'
    )
    db.session.add(new_order)
    db.session.commit()

    for item in data['items']:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item['product_id'],
            quantity=item['quantity']
        )
        db.session.add(order_item)
        product = Product.query.get(item['product_id'])
        product.stock -= item['quantity']

    db.session.commit()
    return jsonify({'message': 'Order created successfully', 'order_id': new_order.id}), 201

@app.route('/orders/<int:customer_id>', methods=['GET'])
def get_customer_orders(customer_id):
    orders = Order.query.filter_by(customer_id=customer_id).all()
    return jsonify([{
        'id': o.id, 'date': o.date, 'total_price': o.total_price,
        'status': o.status
    } for o in orders])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)