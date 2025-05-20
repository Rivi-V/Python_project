from flask import render_template, flash, redirect, url_for, request, current_app, abort
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, SearchForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from sqlalchemy import or_, and_
from sqlalchemy.exc import IntegrityError
from app.models import User, Product, Orders
from datetime import datetime, timezone, date, timedelta 

@app.route('/')
@app.route('/index')
@login_required
def index():
  return render_template("index.html", title='Home Page')

@app.route('/product/<int:product_id>/delete_order/<start_date>', methods=['POST'])
@login_required
def delete_order(product_id, start_date):
    try:
        # Преобразуем строку даты обратно в datetime.date
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Получаем заказ
        if current_user.priority_level == 2:
            order = db.session.execute(
            sa.select(Orders)
            .where(
                Orders.c.product_id == product_id,
                Orders.c.start_date == start_date_obj,
            )
            ).fetchone()
        else:
            order = db.session.execute(
            sa.select(Orders)
            .where(
                Orders.c.product_id == product_id,
                Orders.c.start_date == start_date_obj,
                Orders.c.user_id == current_user.id  # Гарантируем, что пользователь удаляет только свои заказы
            )
            ).fetchone()

        if not order:
            flash('Заказ не найден или у вас нет прав на его удаление', 'danger')
            return redirect(url_for('product', id=product_id))

        # Удаляем заказ
        if current_user.priority_level == 2:
            db.session.execute(
                sa.delete(Orders)
                .where(
                    Orders.c.product_id == product_id,
                    Orders.c.start_date == start_date_obj,
                )
            )
        else:
                db.session.execute(
                sa.delete(Orders)
                .where(
                    Orders.c.product_id == product_id,
                    Orders.c.start_date == start_date_obj,
                    Orders.c.user_id == current_user.id
                )
            )
        db.session.commit()
        flash('Заказ успешно удален', 'success')
    except ValueError:
        flash('Неверный формат даты', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении заказа: {str(e)}', 'danger')
    
    return redirect(url_for('product', id=product_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
  if current_user.is_authenticated:
    return redirect(url_for('index'))
  form = LoginForm()
  if form.validate_on_submit():
    user = db.session.scalar(
      sa.select(User).where(User.username == form.username.data))
    if user is None or not user.check_password(form.password.data):
      flash('Неправильное имя пользователя или пароль')
      return redirect(url_for('login'))
    login_user(user, remember=form.remember_me.data)
    return redirect(url_for('index'))
  return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Поздравляем, вы зарегестрировались!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/explore')
@login_required
def explore():
    type_filter = request.args.get('type', 'all')
    status_filter = request.args.get('status', 'all')
    search_term = request.args.get('query', '')
    page = request.args.get('page', 1, type=int)

    query = sa.select(Product).order_by(Product.id.desc())

    # Фильтр по типу
    if type_filter != 'all':
        query = query.where(Product.type == type_filter)

    # Фильтр по статусу
    if status_filter != 'all':
        query = query.where(Product.status == status_filter)

    # Фильтр по поиску
    if search_term:
        search_term = search_term.strip()
        query = query.where(
            or_(
                Product.name.ilike(f"%{search_term}%"),
                Product.description.ilike(f"%{search_term}%")
            )
        )

    all_types = db.session.execute(
        sa.select(Product.type.distinct()).order_by(Product.type)
    ).scalars().all()

    # Пагинация
    products = db.paginate(
        query,
        page=page,
        per_page=current_app.config['PRODUCTS_PER_PAGE'],
        error_out=False
    )

    return render_template(
        "explore.html",
        title='Поиск товаров',
        products=products.items,
        all_types=all_types,
        current_type=type_filter,
        current_status=status_filter,
        search_term=search_term,
        next_url=url_for('explore', 
                       page=products.next_num,
                       type=type_filter,
                       status=status_filter,
                       query=search_term) if products.has_next else None,
        prev_url=url_for('explore',
                       page=products.prev_num,
                       type=type_filter,
                       status=status_filter,
                       query=search_term) if products.has_prev else None
    )

@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    
    page = request.args.get('page', 1, type=int) # номер страницы из параметров запроса
    
    # запрос, новые сначала
    query = (
        sa.select(Product) # создаём запрос
        .join(Orders, Product.id == Orders.c.product_id) # выбираем те продукты, которые из в заказах
        .where(Orders.c.user_id == user.id) # в заказах, которые сделал юзер
        .order_by(Orders.c.start_date.desc()) # сортируем по началу аренды
    )
    
    # пагинация
    products = db.paginate(
        query,
        page=page,
        per_page=current_app.config['PRODUCTS_PER_PAGE'],
        error_out=False
    )
    
    # генерация URL для навигации
    next_url = url_for('user', username=username, page=products.next_num) \
        if products.has_next else None
    prev_url = url_for('user', username=username, page=products.prev_num) \
        if products.has_prev else None
    
    return render_template(
        'user.html',
        user=user,
        products=products.items,
        next_url=next_url,
        prev_url=prev_url
    )

@app.route('/product/<int:id>', methods=['GET', 'POST'])
@login_required
def product(id):
    # aвтоматическое обновление просроченных заказов
    today = datetime.now().date()
    expired_orders = db.session.execute(
        sa.select(Orders)
        .where(
            Orders.c.status == 'active',
            Orders.c.end_date < today
        )
    ).fetchall()

    for order_row in expired_orders:
        user_id = order_row.user_id
        product_id = order_row.product_id
        start_date = order_row.start_date
        
        db.session.execute(
            sa.update(Orders)
            .where(
                Orders.c.user_id == user_id,
                Orders.c.product_id == product_id,
                Orders.c.start_date == start_date
            )
            .values(status='inactive')
        )

    if expired_orders:
        db.session.commit()
    
    db.session.execute( # выполнение запросы
        sa.update(Product) # обновление бд
        .where( # условие фильтрации
            Product.id.in_( # будут обновлены те строки, которые соответствуют условиям
                sa.select(Orders.c.product_id) # получаем список индетификаторов проодуктов, связанных с активными арендами
                .where(
                    and_(
                        Orders.c.start_date <= datetime.now().date(),
                        Orders.c.end_date >= datetime.now().date(),
                        Orders.c.status == 'active'  # только активные аренды
                    )
                )
            )
        )
        .values(status='Rented') # обновляем статус продукта
    )
    db.session.commit()

    # то же самое 

    db.session.execute(
        sa.update(Product)
        .where(
            and_(
                Product.status != 'Free',
                ~Product.id.in_(
                    sa.select(Orders.c.product_id)
                    .where(
                        and_(
                            Orders.c.start_date <= datetime.now().date(),
                            Orders.c.end_date >= datetime.now().date(),
                            Orders.c.status == 'active'
                        )
                    )
                )
            )
        )
        .values(status='Free')
    )
    db.session.commit()

    product = db.session.execute(db.select(Product).where(Product.id == id)).scalar_one_or_none()
    if product is None:
        abort(404)
    
    # получаем все заказы для этого продукта
    first_day_of_current_month = datetime.now().replace(day=1).date()

    # Вычисляем дату 2 месяца назад от текущей даты
    two_months_ago = datetime.now().date() - timedelta(days=60)
    
    # Получаем все заказы для этого продукта за последние 2 месяца
    orders = db.session.execute(
        sa.select(Orders)
        .where(
            and_(
                Orders.c.product_id == id,
                Orders.c.start_date >= two_months_ago  # Заказы не старше 2 месяцев
            )
        )
        .order_by(Orders.c.start_date.desc())  # Сортировка от новых к старым
    ).fetchall()
    
    if request.method == 'POST':
        if current_user.priority_level == 0:
            flash('У вас недостаточно прав для создания заказов', 'danger')
            return redirect(url_for('product', id=id))

        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        location = request.form['location']

        if start_date < datetime.now().date():
            flash('Дата начала не может быть раньше текущей даты', 'error')
            return redirect(url_for('product', id=id))  # или другой подходящий обработчик

        if end_date < start_date:
            flash('Дата окончания не может быть раньше даты начала', 'error')
            return redirect(url_for('product', id=id))
        
        conflicting_orders = db.session.execute(
            sa.select(Orders)
            .where(Orders.c.product_id == id)
            .where(Orders.c.status == 'active')
            .where(
                or_(
                    and_(Orders.c.start_date <= end_date, Orders.c.end_date >= start_date),
                )
            )
        ).fetchall()

        # если есть конфликты, проверяем приоритеты
        has_higher_priority = False
        orders_to_deactivate = []

        for order in conflicting_orders:
            user = db.session.get(User, order.user_id)
            if user.priority_level < current_user.priority_level:
                orders_to_deactivate.append(order)
            else:
                has_higher_priority = True

        if has_higher_priority:
            flash('Выбранные даты уже заняты пользователем с более высоким приоритетом.', 'danger')
            return redirect(url_for('product', id=id))

        # деактивируем заказы с меньшим приоритетом
        for order in orders_to_deactivate:
            db.session.execute(
                sa.update(Orders)
                .where(Orders.c.user_id == order.user_id)
                .where(Orders.c.product_id == id)
                .where(Orders.c.start_date == order.start_date)
                .values(status='inactive')
            )

        # добавляем новый заказ
        try:
            db.session.execute(
                sa.delete(Orders)
                .where(Orders.c.user_id == current_user.id)
                .where(Orders.c.product_id == id)
                .where(Orders.c.status == 'inactive')  # Удаляем только неактивные
            ) 
            db.session.execute(
                sa.insert(Orders).values(
                    user_id=current_user.id,
                    product_id=id,
                    start_date=start_date,
                    end_date=end_date,
                    location=location,
                    status='active'
                )
            )
            db.session.commit()
            flash('Заказ успешно создан!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Вы уже находитесь в очереди на аренду товара.', 'danger')
        return redirect(url_for('product', id=id))
    
    return render_template('product.html', product=product, orders=orders)
    

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Профиль изменён.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)
