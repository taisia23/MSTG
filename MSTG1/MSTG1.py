from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import requests
import asyncio
from datetime import datetime
from server import app

TOKEN = "7378908588:AAFAAuAGPt-F9kWc9N0MNyz-QPElp6EyFYA"
BASE_URL = "http://localhost:5000"

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

class CustomerRegistration(StatesGroup):
    waiting_for_contact = State()
    waiting_for_role = State()

class ManagerRegistration(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_phone = State()

# Створимо словники для меню, щоб уникнути дублювання коду
menus = {
    "user": ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🏍 Каталог товарів')],
            [KeyboardButton(text='🛒 Кошик'), KeyboardButton(text='📦 Мої замовлення')],
            [KeyboardButton(text='👤 Особистий кабінет'), KeyboardButton(text='ℹ️ Про магазин')],
            [KeyboardButton(text='👨‍💼 Режим менеджера')]
        ],
        resize_keyboard=True
    ),
    "manager": ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🏍 Каталог товарів')],
            [KeyboardButton(text='➕ Додати товар'), KeyboardButton(text='📊 Статистика продажів')],
            [KeyboardButton(text='👥 Клієнти'), KeyboardButton(text='ℹ️ Про магазин')],
            [KeyboardButton(text='👤 Режим покупця')]
        ],
        resize_keyboard=True
    )
}
@router.message(Command(commands=['start']))
async def send_welcome(message: types.Message, state: FSMContext):
    response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
    if response.status_code == 200:
        customer = response.json()
        is_manager = customer.get('is_manager', False)
        menu = menus["manager"] if is_manager else menus["user"]
        await message.answer("🏍 Вітаємо у MotoShopTG! Оберіть опцію з меню нижче:", reply_markup=menu)
    else:
        await state.set_state(CustomerRegistration.waiting_for_contact)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Поділитися номером телефону", request_contact=True)]],
            resize_keyboard=True
        )
        await message.answer("Схоже, ви ще не зареєстровані. Будь ласка, поділіться вашим номером телефону або введіть ваш нікнейм в Telegram:", reply_markup=keyboard)

@router.message(CustomerRegistration.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext):
    if message.contact is not None:
        contact = message.contact.phone_number
    else:
        contact = message.text

    # Перевіряємо, чи існує вже користувач із таким telegram_id або contact
    existing_customer = requests.get(f"{BASE_URL}/customers/check", params={"telegram_id": message.from_user.id, "contact": contact})
    if existing_customer.status_code == 200:
        await message.answer("Ви вже зареєстровані. Оберіть опцію з меню нижче:", reply_markup=menus["user"])
        await state.clear()
        return

    await state.update_data(contact=contact)
    await state.set_state(CustomerRegistration.waiting_for_role)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Покупець")],
            [KeyboardButton(text="Менеджер")]
        ],
        resize_keyboard=True
    )
    await message.answer("Оберіть вашу роль:", reply_markup=keyboard)

@router.message(CustomerRegistration.waiting_for_role)
async def process_role(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    is_manager = message.text.lower() == "менеджер"
    
    user_data.update({
        "telegram_id": message.from_user.id,
        "contact": user_data['contact'],
        "is_manager": is_manager
    })
    
    response = requests.post(f"{BASE_URL}/customers", json=user_data)
    
    if response.status_code == 201:
        menu = menus["manager"] if is_manager else menus["user"]
        await message.answer("Дякуємо за реєстрацію! Ви успішно додані до нашої системи.", reply_markup=menu)
    else:
        await message.answer("На жаль, виникла помилка при реєстрації. Будь ласка, спробуйте ще раз пізніше.")
    
    await state.clear()

@router.message(lambda message: message.text in ['👨‍💼 Режим менеджера', '👤 Режим покупця'])
async def switch_role(message: types.Message):
    response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
    if response.status_code == 200:
        customer = response.json()
        is_manager = not customer.get('is_manager', False)  # Перемикаємо роль
        
        # Оновлюємо роль користувача в базі даних
        update_response = requests.put(f"{BASE_URL}/customers/{message.from_user.id}", json={"is_manager": is_manager})
        
        if update_response.status_code == 200:
            menu = menus["manager"] if is_manager else menus["user"]
            role = "менеджера" if is_manager else "покупця"
            await message.answer(f"Ви успішно переключилися в режим {role}.", reply_markup=menu)
        else:
            await message.answer("На жаль, виникла помилка при зміні режиму. Спробуйте пізніше.")
    else:
        await message.answer("На жаль, виникла помилка. Спробуйте пізніше.")

@router.message(Command(commands=['register_manager']))
async def register_manager(message: types.Message, state: FSMContext):
    try:
        # Перевіряємо, чи є в нас уже такий менеджер або клієнт із таким telegram_id
        response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
        if response.status_code == 200:
            customer_data = response.json()
            if customer_data.get('is_manager', False):
                await message.answer("Ви вже зареєстровані як менеджер.")
                return 

            # Якщо це наявний клієнт, але не менеджер, оновлюємо його дані та створюємо запис у таблиці менеджерів
            customer_data["is_manager"] = True
            response = requests.put(f"{BASE_URL}/customers/{message.from_user.id}", json=customer_data)
            if response.status_code != 200:
                await message.answer("На жаль, сталася помилка при оновленні даних користувача. Будь ласка, спробуйте пізніше.")
                return

            manager_data = {
                "telegram_id": message.from_user.id,
                "first_name": customer_data.get('first_name', message.from_user.first_name),
                "last_name": customer_data.get('last_name', message.from_user.last_name),
                "phone": customer_data.get('phone', None)
            }
            response = requests.post(f"{BASE_URL}/managers", json=manager_data)
            if response.status_code == 201:
                await message.answer("Ви успішно зареєстровані як менеджер!", reply_markup=menus["manager"])
            else:
                await message.answer("На жаль, сталася помилка при реєстрації менеджера. Будь ласка, спробуйте пізніше.")

        else: 
            # Якщо це новий користувач, спочатку реєструємо його як клієнта, потім як менеджера
            await state.set_state(ManagerRegistration.waiting_for_phone)
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Поділитися номером телефону", request_contact=True)]],
                resize_keyboard=True
            )
            await message.answer("Спочатку потрібно зареєструватися як користувач. Будь ласка, поділіться вашим номером телефону:", reply_markup=keyboard)

    except Exception as e:
        app.logger.error(f"Error registering manager: {e}")
        await message.answer("На жаль, сталася помилка при реєстрації. Будь ласка, спробуйте пізніше.")

@router.message(ManagerRegistration.waiting_for_phone)
async def process_manager_phone(message: types.Message, state: FSMContext):
    try:
        if message.contact is not None:
            phone = message.contact.phone_number
        else:
            phone = message.text 

        # Створюємо запис клієнта
        customer_data = {
            "telegram_id": message.from_user.id,
            "contact": phone,
            "is_manager": True,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "phone": phone
        }
        response = requests.post(f"{BASE_URL}/customers", json=customer_data)
        if response.status_code != 201:
            await message.answer("На жаль, сталася помилка при реєстрації користувача. Будь ласка, спробуйте пізніше.")
            return

        # Створюємо запис менеджера
        manager_data = {
            "telegram_id": message.from_user.id,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "phone": phone
        }
        response = requests.post(f"{BASE_URL}/managers", json=manager_data)
        if response.status_code == 201:
            await message.answer("Ви успішно зареєстровані як менеджер!", reply_markup=menus["manager"])
        else:
            await message.answer("На жаль, сталася помилка при реєстрації менеджера. Будь ласка, спробуйте пізніше.")

        await state.clear()
    except Exception as e:
        app.logger.error(f"Error processing manager phone: {e}")
        await message.answer("На жаль, сталася помилка при обробці номера телефону. Будь ласка, спробуйте пізніше.")

@router.message(Command(commands=['manager']))
async def manager_login(message: types.Message):
    try:
        # Отримуємо дані клієнта за telegram_id
        response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
        if response.status_code == 200:
            customer_data = response.json()
            if customer_data.get('is_manager', False):
                # Перевіряємо, чи є запис у таблиці менеджерів
                response = requests.get(f"{BASE_URL}/managers/{message.from_user.id}")
                if response.status_code == 200:
                    await message.answer("Ви успішно увійшли як менеджер!", reply_markup=menus["manager"])
                else:
                    await message.answer("Виникла помилка при вході. Будь ласка, зверніться до адміністратора.")
            else:
                await message.answer("Ви не є зареєстрованим менеджером.")
        else:
            await message.answer("Ви не є зареєстрованим користувачем.")
    except Exception as e:
        app.logger.error(f"Error during manager login: {e}")
        await message.answer("На жаль, сталася помилка під час входу. Будь ласка, спробуйте пізніше.")

class ProductAddition(StatesGroup):
    waiting_for_name = State()
    waiting_for_category = State()
    waiting_for_manufacturer = State()
    waiting_for_model = State()
    waiting_for_year = State()
    waiting_for_stock = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_image_url = State()

@router.message(lambda message: message.text == '🏍 Каталог товарів')
async def view_catalog(message: types.Message):
    response = requests.get(f"{BASE_URL}/products")
    products = response.json()
    
    categories = set(p['category'] for p in products)
    buttons = []
    for category in categories:
        buttons.append([InlineKeyboardButton(text=category, callback_data=f"category_{category}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer("Оберіть категорію товару:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith('category_'))
async def process_category(callback_query: types.CallbackQuery):
    category = callback_query.data.split('_')[1]
    response = requests.get(f"{BASE_URL}/products")
    products = [p for p in response.json() if p['category'] == category]
    
    for product in products:
        buttons = [[InlineKeyboardButton(
            text="Додати до кошика", 
            callback_data=f"add_to_cart_{product['id']}"
        )]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await bot.send_message(
            callback_query.from_user.id,
            f"🏍 {product['name']}\n"
            f"💰 Ціна: {product['price']} грн\n"
            f"📦 В наявності: {product['stock']} шт.\n"
            f"ℹ️ {product['description']}",
            reply_markup=keyboard
        )

@router.callback_query(lambda c: c.data.startswith('add_to_cart_'))
async def add_to_cart(callback_query: types.CallbackQuery, state: FSMContext):
    product_id = int(callback_query.data.split('_')[3])
    cart = await state.get_data()
    cart_items = cart.get('cart', [])
    cart_items.append(product_id)
    await state.update_data(cart=cart_items)
    await bot.answer_callback_query(callback_query.id, text="Товар додано до кошика!")

@router.message(lambda message: message.text == '🛒 Кошик')
async def view_cart(message: types.Message, state: FSMContext):
    cart = await state.get_data()
    cart_items = cart.get('cart', [])
    if not cart_items:
        await message.answer("Ваш кошик порожній. Додайте товари з каталогу!")
    else:
        response = requests.get(f"{BASE_URL}/products")
        products = {p['id']: p for p in response.json()}
        cart_content = "Ваш кошик:\n\n"
        total_price = 0
        for product_id in cart_items:
            product = products[product_id]
            cart_content += f"🏍 {product['name']} - {product['price']} грн\n"
            total_price += product['price']
        cart_content += f"\nЗагальна сума: {total_price} грн"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Оформити замовлення", callback_data="checkout")]])
        await message.answer(cart_content, reply_markup=keyboard)

@router.callback_query(lambda c: c.data == 'checkout')
async def checkout(callback_query: types.CallbackQuery, state: FSMContext):
    cart = await state.get_data()
    cart_items = cart.get('cart', [])
    
    if not cart_items:
        await bot.answer_callback_query(callback_query.id, text="Ваш кошик порожній!")
        return

    response = requests.get(f"{BASE_URL}/products")
    products = {p['id']: p for p in response.json()}
    
    order_items = []
    total_price = 0
    for product_id in cart_items:
        product = products[product_id]
        order_items.append({
            "product_id": product_id,
            "quantity": 1
        })
        total_price += product['price']

    order_data = {
        "customer_id": callback_query.from_user.id,
        "total_price": total_price,
        "items": order_items
    }

    response = requests.post(f"{BASE_URL}/orders", json=order_data)
    
    if response.status_code == 201:
        await state.update_data(cart=[])
        await bot.send_message(callback_query.from_user.id, "Замовлення оформлено! Дякуємо за покупку.")
    else:
        await bot.send_message(callback_query.from_user.id, "На жаль, виникла помилка при оформленні замовлення. Спробуйте пізніше.")

@router.message(lambda message: message.text == '📦 Мої замовлення')
async def view_orders(message: types.Message):
    response = requests.get(f"{BASE_URL}/orders/{message.from_user.id}")
    orders = response.json()
    if orders:
        orders_text = "Ваші замовлення:\n\n"
        for order in orders:
            orders_text += f"Замовлення #{order['id']}\n"
            orders_text += f"Дата: {order['date']}\n"
            orders_text += f"Сума: {order['total_price']} грн\n"
            orders_text += f"Статус: {order['status']}\n\n"
        await message.answer(orders_text)
    else:
        await message.answer("У вас ще немає замовлень.")

@router.message(lambda message: message.text == '👤 Особистий кабінет')
async def personal_cabinet(message: types.Message):
    response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
    if response.status_code == 200:
        customer = response.json()
        profile_text = f"👤 Ваш особистий кабінет:\n\n"
        profile_text += f"Ім'я: {customer.get('first_name', 'Не вказано')}\n"
        profile_text += f"Прізвище: {customer.get('last_name', 'Не вказано')}\n"
        profile_text += f"Телефон: {customer.get('phone', 'Не вказано')}\n"
        profile_text += f"Email: {customer.get('email', 'Не вказано')}\n"
        profile_text += f"Дата народження: {customer.get('birth_date', 'Не вказано')}\n"
        
        edit_profile_button = InlineKeyboardButton(text="Редагувати профіль", callback_data="edit_profile")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[edit_profile_button]])
        await message.answer(profile_text, reply_markup=keyboard)
    else:
        await message.answer("На жаль, не вдалося отримати дані вашого профілю. Спробуйте пізніше.")

@router.message(lambda message: message.text == '➕ Додати товар')
async def add_product(message: types.Message, state: FSMContext):
    # Перевіряємо, чи є користувач менеджером
    response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
    if response.status_code == 200:
        customer = response.json()
        if customer.get('is_manager', False):
            await state.set_state(ProductAddition.waiting_for_name)
            await message.answer("Введіть назву нового товару:")
        else:
            await message.answer("У вас немає прав для додавання товарів.")
    else:
        await message.answer("Помилка перевірки прав доступу. Спробуйте пізніше.")



@router.message(lambda message: message.text == 'ℹ️ Про магазин')
async def about_shop(message: types.Message):
    about_text = (
        "🏍 MotoShopTG - ваш надійний партнер у світі мотоциклів!\n\n"
        "Ми пропонуємо широкий вибір мотоциклів, запчастин та аксесуарів "
        "від провідних світових виробників.\n\n"
        "🌟 Наші переваги:\n"
        "✅ Великий асортимент товарів\n"
        "✅ Професійні консультації\n"
        "✅ Швидка доставка по всій країні\n"
        "✅ Гарантія на всі товари\n\n"
        "📞 Контакти:\n"
        "Телефон: +380123456789\n"
        "Email: info@motoshoptg.com\n"
        "Адреса: м. Київ, вул. Мотоциклетна, 123"
    )
    await message.answer(about_text)



@router.message(ProductAddition.waiting_for_name)
async def process_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ProductAddition.waiting_for_category)
    await message.answer("Введіть категорію товару:")

@router.message(ProductAddition.waiting_for_category)
async def process_product_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(ProductAddition.waiting_for_manufacturer)
    await message.answer("Введіть виробника товару:")

@router.message(ProductAddition.waiting_for_manufacturer)
async def process_product_manufacturer(message: types.Message, state: FSMContext):
    await state.update_data(manufacturer=message.text)
    await state.set_state(ProductAddition.waiting_for_model)
    await message.answer("Введіть модель товару:")

@router.message(ProductAddition.waiting_for_model)
async def process_product_model(message: types.Message, state: FSMContext):
    await state.update_data(model=message.text)
    await state.set_state(ProductAddition.waiting_for_year)
    await message.answer("Введіть рік випуску товару:")

@router.message(ProductAddition.waiting_for_year)
async def process_product_year(message: types.Message, state: FSMContext):
    try:
        year = int(message.text)
        await state.update_data(year=year)
        await state.set_state(ProductAddition.waiting_for_stock)
        await message.answer("Введіть кількість товару на складі:")
    except ValueError:
        await message.answer("Будь ласка, введіть коректний рік (ціле число):")

@router.message(ProductAddition.waiting_for_stock)
async def process_product_stock(message: types.Message, state: FSMContext):
    try:
        stock = int(message.text)
        await state.update_data(stock=stock)
        await state.set_state(ProductAddition.waiting_for_price)
        await message.answer("Введіть ціну товару:")
    except ValueError:
        await message.answer("Будь ласка, введіть коректну кількість (ціле число):")

@router.message(ProductAddition.waiting_for_price)
async def process_product_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await state.set_state(ProductAddition.waiting_for_description)
        await message.answer("Введіть опис товару:")
    except ValueError:
        await message.answer("Будь ласка, введіть коректну ціну (число):")

@router.message(ProductAddition.waiting_for_description)
async def process_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(ProductAddition.waiting_for_image_url)
    await message.answer("Введіть URL зображення товару:")

@router.message(ProductAddition.waiting_for_image_url)
async def process_product_image_url(message: types.Message, state: FSMContext):
    await state.update_data(image_url=message.text)
    product_data = await state.get_data()
    
    # Перевіряємо обов'язкові поля
    required_fields = ["name", "category", "manufacturer", "model", "year", "stock", "price", "description"]
    if not all(field in product_data for field in required_fields):
        await message.answer("Не всі обов'язкові поля заповнені. Будь ласка, почніть додавання товару знову.")
        await state.clear()
        return

    response = requests.post(f"{BASE_URL}/products", json=product_data)
    
    if response.status_code == 201:
        await message.answer("Товар успішно додано до каталогу!")
    else:
        await message.answer("На жаль, виникла помилка при додаванні товару. Спробуйте пізніше.")
    
    await state.clear()

@router.message(lambda message: message.text == '📊 Статистика продажів')
async def sales_statistics(message: types.Message):
    # Перевіряємо, чи є користувач менеджером
    response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
    if response.status_code == 200:
        customer = response.json()
        if customer.get('is_manager', False):
            # Отримуємо статистику продажів
            response = requests.get(f"{BASE_URL}/sales_statistics")
            if response.status_code == 200:
                stats = response.json()
                stats_text = "📊 Статистика продажів:\n\n"
                stats_text += f"Загальна кількість замовлень: {stats.get('total_orders', 'Немає даних')}\n"
                stats_text += f"Загальна сума продажів: {stats.get('total_sales', 'Немає даних')} грн\n"
                stats_text += f"Середній чек: {stats.get('average_order_value', 'Немає даних')} грн\n"
                stats_text += f"Найпопулярніший товар: {stats.get('top_selling_product', 'Немає даних')}\n"
                await message.answer(stats_text)
            else:
                await message.answer("На жаль, не вдалося отримати статистику продажів. Спробуйте пізніше.")
        else:
            await message.answer("У вас немає прав для перегляду статистики продажів.")
    else:
        await message.answer("Помилка перевірки прав доступу. Спробуйте пізніше.")

@router.message(lambda message: message.text == '👥 Клієнти')
async def view_customers(message: types.Message):
    # Перевіряємо, чи є користувач менеджером
    response = requests.get(f"{BASE_URL}/customers/{message.from_user.id}")
    if response.status_code == 200:
        customer = response.json()
        if customer.get('is_manager', False):
            # Отримуємо список клієнтів
            response = requests.get(f"{BASE_URL}/customers")
            if response.status_code == 200:
                customers = response.json()
                customers_text = "👥 Список клієнтів:\n\n"
                for customer in customers:
                    customers_text += f"ID: {customer.get('id', 'Не вказано')}\n"
                    customers_text += f"Ім'я: {customer.get('first_name', 'Не вказано')} {customer.get('last_name', 'Не вказано')}\n"
                    customers_text += f"Телефон: {customer.get('phone', 'Не вказано')}\n\n"
                await message.answer(customers_text)
            else:
                await message.answer("На жаль, не вдалося отримати список клієнтів. Спробуйте пізніше.")
        else:
            await message.answer("У вас немає прав для перегляду списку клієнтів.")
    else:
        await message.answer("Помилка перевірки прав доступу. Спробуйте пізніше.")

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())