from datetime import datetime, timezone
from typing import Optional
from app import db, login

from flask_login import UserMixin

# DB
import sqlalchemy as sa
import sqlalchemy.orm as so

# Хэширование паролей
from werkzeug.security import generate_password_hash, check_password_hash

Orders = sa.Table(
    'orders',
    db.metadata,
    sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True),
    sa.Column('product_id', sa.Integer, sa.ForeignKey('product.id'), primary_key=True),
    sa.Column('start_date', sa.Date, nullable=False),  # Используем Date вместо DateTime
    sa.Column('end_date', sa.Date, nullable=False),    # Используем Date вместо DateTime
    sa.Column('location', sa.String(200), nullable=False),
    sa.Column('status', sa.String(20), server_default='active')
)

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    products = so.relationship(
        'Product',
        secondary=Orders,  # Указываем ассоциативную таблицу
        back_populates='users',  # Связываем с полем `users` в модели Product
        lazy='dynamic'  # Опция загрузки данных
    )

    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    

class Product(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(200), index=True, unique=True)
    type: so.Mapped[str] = so.mapped_column(sa.String(200), index=True)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.String(400))
    status: so.Mapped[Optional[str]] = so.mapped_column(sa.String(400), default="Free")
    image_url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(500), default="")  # Новое поле для URL изображения

    users = so.relationship(
        'User',
        secondary=Orders,  # Указываем ассоциативную таблицу
        back_populates='products',  # Связываем с полем `products` в модели User
        lazy='dynamic'  # Опция загрузки данных
    )


# добавляем заказы явно, а не через отношения (users или products) -> ошибка
# как надо например:

# from datetime import datetime

# order2 = Orders.insert().values(
#     user_id=user1.id,
#     product_id=product2.id,
#     start_date=datetime.utcnow(),
#     end_date=datetime.utcnow(),
#     location="Warehouse B"
# )
# db.session.execute(order1)
# db.session.commit()