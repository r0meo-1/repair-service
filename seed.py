from app.database import SessionLocal, engine
from app.models import Base, User, Request, StatusEnum
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

Base.metadata.create_all(bind=engine)

db = SessionLocal()

users = [
    User(username='dispatcher', password_hash=pwd_context.hash('pass123'), role='dispatcher'),
    User(username='master1', password_hash=pwd_context.hash('pass123'), role='master'),
    User(username='master2', password_hash=pwd_context.hash('pass123'), role='master'),
]

for u in users:
    existing = db.query(User).filter(User.username == u.username).first()
    if not existing:
        db.add(u)

db.commit()

requests_data = [
    Request(clientName='Ivan Ivanov', phone='+71234567890', address='Moscow, 1', problemText='Leaking pipe', status=StatusEnum.new),
    Request(clientName='Maria Sidorova', phone='+79876543210', address='SPb, 5', problemText='No electricity', status=StatusEnum.new),
]

for r in requests_data:
    db.add(r)

db.commit()
db.close()
print('Seed completed successfully')
