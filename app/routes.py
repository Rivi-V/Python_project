from flask import render_template, flash, redirect, url_for, request, current_app, abort
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, SearchForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from sqlalchemy import or_, and_
from app.models import User, Product, Orders
from datetime import datetime, timezone, date, timedelta 

@app.route('/')
@app.route('/index')
@login_required
def index():
  return render_template("index.html", title='Home Page')

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


@app.route('/explore', methods=['GET', 'POST'])
@login_required
def explore():
    form = SearchForm()
    
    query = sa.select(Product).order_by(Product.id.desc())

    if form.validate_on_submit():
        search_term = form.query.data.strip()  # удаляем пробелы
        if search_term:
            query = query.where(Product.name.ilike(f"%{search_term}%")) # товары, где название содержит слово
            flash(f'Найдены товары по запросу "{search_term}"')
        else:
            flash('Введите поисковый запрос')

    page = request.args.get('page', 1, type=int) # пагинация
    products = db.paginate(
        query,
        page=page,
        per_page=current_app.config['PRODUCTS_PER_PAGE'],
        error_out=False
    )

    next_url = url_for('explore', page=products.next_num) if products.has_next else None
    prev_url = url_for('explore', page=products.prev_num) if products.has_prev else None

    return render_template(
        "explore.html",
        title='Поиск товаров',
        products=products.items,
        next_url=next_url,
        prev_url=prev_url,
        form=form,
        search_term=form.query.data if form.validate_on_submit() else None
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

    orders = db.session.execute(
        sa.select(Orders).where(
            and_(
                Orders.c.product_id == id,
                or_(
                    # Текущие заказы (которые активны и даты в пределах текущего времени)
                    and_(
                        Orders.c.start_date <= datetime.now().date(),
                        Orders.c.end_date >= datetime.now().date(),
                        Orders.c.status == 'active'
                    ),
                    # Прошедшие заказы, но созданные в текущем месяце
                    and_(
                        Orders.c.end_date < datetime.now().date(),
                        Orders.c.start_date >= first_day_of_current_month
                    )
                )
            )
        )
        .order_by(Orders.c.start_date)
    ).all()
    
    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        location = request.form['location']
        
        # проверяем есть ли уже заказ этого пользователя на этот продукт
        existing_order = db.session.execute(
            sa.select(Orders)
            .where(Orders.c.user_id == current_user.id)
            .where(Orders.c.product_id == id)
        ).first()
        
        if existing_order:
            flash('Вы уже находитсь в очереди на аренду товара.', 'danger')
            return redirect(url_for('product', id=id))
        
        # проверяем пересечение дат с активными заказами
        conflicting_orders = db.session.execute(
            sa.select(Orders)
            .where(Orders.c.product_id == id)
            .where(Orders.c.status == 'active')
            .where(
                or_(
                    and_(Orders.c.start_date <= end_date, Orders.c.end_date >= start_date),
                )
            )
        ).all()
        
        # если есть конфликты, проверяем приоритеты
        if conflicting_orders:
            for order in conflicting_orders:
                user = db.session.get(User, order.user_id)
                if user.priority_level < current_user.priority_level:
                    # деактивируем заказ с меньшим приоритетом
                    db.session.execute(
                        sa.update(Orders)
                        .where(Orders.c.user_id == order.user_id)
                        .where(Orders.c.product_id == id)
                        .where(Orders.c.start_date == order.start_date)
                        .values(status='inactive')
                    )
                else:
                    flash('Выбранную дату уже выбрал пользвоатель с более высоким приоритетом.', 'danger')
                    return redirect(url_for('product', id=id))
        
        # добавляем новый заказ (учитывая возможную ошибку с несколькими заказами)
        try:
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
        except IntegrityError:
            db.session.rollback()
            flash('Вы уже находитсь в очереди на аренду товара.', 'danger')
        
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