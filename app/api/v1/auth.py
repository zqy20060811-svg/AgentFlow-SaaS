from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Plan, PlanTier, Subscription, User
from app.schemas import TokenOut, UserLogin, UserOut, UserRegister
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _ensure_plans_exist(db: Session):
    """首次启动时自动播种套餐数据"""
    if db.query(Plan).count() > 0:
        return
    plans = [
        Plan(tier="free", name="免费版", price_cents=0, monthly_quota=10,
             description="每月10次生成"),
        Plan(tier="pro", name="专业版", price_cents=2900, monthly_quota=500,
             description="每月500次生成，29元/月"),
        Plan(tier="ultra", name="旗舰版", price_cents=9900, monthly_quota=2000,
             description="每月2000次生成，99元/月"),
    ]
    db.add_all(plans)
    db.commit()


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    # 检查邮箱是否已注册
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    # 创建用户
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    db.flush()

    # 自动分配 free 套餐
    _ensure_plans_exist(db)
    free_plan = db.query(Plan).filter(Plan.tier == PlanTier.free.value).first()
    sub = Subscription(
        user_id=user.id,
        plan_id=free_plan.id,
        remaining_quota=free_plan.monthly_quota,
    )
    db.add(sub)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = _authenticate(db, payload.email, payload.password)
    token = create_access_token({"sub": str(user.id)})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def login_for_docs(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 表单登录，专供 Swagger UI 的 Authorize 按钮使用，username 填邮箱"""
    user = _authenticate(db, form_data.username, form_data.password)
    token = create_access_token({"sub": str(user.id)})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
