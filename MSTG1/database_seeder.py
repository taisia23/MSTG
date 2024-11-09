import sys
import os

# Додайте шлях до директорії з вашим основним додатком
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app, db, Product, Customer, Manager, Order, OrderItem
from datetime import datetime, timedelta
import random

def seed_database():
    with app.app_context():
        # Очищення бази даних
        db.drop_all()
        db.create_all()

        # Створення продуктів (без змін)
        products = [
            Product(name="Yamaha YZF-R1", category="Спортбайк", manufacturer="Yamaha", model="YZF-R1", year=2023, stock=5, price=15000, description="Потужний спортивний мотоцикл", image_url="https://example.com/yzf-r1.jpg"),
            Product(name="Harley-Davidson Street Glide", category="Круізер", manufacturer="Harley-Davidson", model="Street Glide", year=2023, stock=3, price=20000, description="Комфортний круізер для довгих поїздок", image_url="https://example.com/street-glide.jpg"),
            Product(name="BMW R 1250 GS", category="Ендуро", manufacturer="BMW", model="R 1250 GS", year=2023, stock=7, price=18000, description="Універсальний мотоцикл для будь-яких доріг", image_url="https://example.com/r1250gs.jpg"),
            Product(name="Ducati Panigale V4", category="Спортбайк", manufacturer="Ducati", model="Panigale V4", year=2023, stock=2, price=25000, description="Екстремально швидкий спортбайк", image_url="https://example.com/panigale-v4.jpg"),
            Product(name="Honda Africa Twin", category="Ендуро", manufacturer="Honda", model="Africa Twin", year=2023, stock=4, price=14000, description="Надійний мотоцикл для пригод", image_url="https://example.com/africa-twin.jpg")
        ]
        db.session.add_all(products)
        db.session.commit()

        # Створення клієнтів (оновлено)
        customers = [
            Customer(telegram_id=11111, contact='+380991234567', first_name="Іван", last_name="Петренко", phone="+380991234567", birth_date=datetime(1990, 5, 15)),
            Customer(telegram_id=22222, contact='+380992345678', first_name="Олена", last_name="Коваленко", phone="+380992345678", birth_date=datetime(1985, 8, 22)),
            Customer(telegram_id=33333, contact='+380993456789', first_name="Микола", last_name="Сидоренко", phone="+380993456789", birth_date=datetime(1992, 3, 10))
        ]
        db.session.add_all(customers)
        db.session.commit()

        # Створення менеджера
        manager = Manager(telegram_id=44444, first_name="Адміністратор", last_name="Магазину", phone="+380501112233")
        db.session.add(manager)
        db.session.commit()

        # Створення замовлень (оновлено для використання telegram_id)
        for _ in range(10):
            customer = random.choice(customers)
            order = Order(
                customer_id=customer.id,
                date=datetime.now() - timedelta(days=random.randint(1, 30)),
                total_price=0,
                status=random.choice(["Обробляється", "Відправлено", "Доставлено"])
            )
            db.session.add(order)
            db.session.flush()

            # Додавання товарів у замовлення (без змін)
            order_items = []
            for _ in range(random.randint(1, 3)):
                product = random.choice(products)
                quantity = random.randint(1, 3)
                order_item = OrderItem(order_id=order.id, product_id=product.id, quantity=quantity)
                order_items.append(order_item)
                order.total_price += product.price * quantity

            db.session.add_all(order_items)

        db.session.commit()
        print("База даних успішно заповнена тестовими даними.")

if __name__ == "__main__":
    seed_database()