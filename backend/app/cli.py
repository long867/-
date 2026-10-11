"""Operator commands with interactive passwords."""

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.core.db import SessionFactory
from app.core.security import hash_password
from app.models import User
from app.schemas.api import Credentials


async def create_admin(email: str) -> None:
    """Provision administration explicitly; never ship a default admin password."""
    password = getpass.getpass("Admin password (at least 10 characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise ValueError("Passwords do not match")
    credentials = Credentials(email=email, password=password)
    async with SessionFactory.begin() as db:
        existing = await db.scalar(select(User).where(User.email == credentials.email))
        if existing:
            raise ValueError(
                "User already exists; modify privileges via audited DB access"
            )
        db.add(
            User(
                email=credentials.email,
                password_hash=hash_password(password),
                is_admin=True,
            )
        )
    print("Administrator created.")


def main() -> None:
    """Run the selected operator command."""
    parser = argparse.ArgumentParser(description="MiningIntel operator CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin")
    admin.add_argument("email")
    arguments = parser.parse_args()
    if arguments.command == "create-admin":
        asyncio.run(create_admin(arguments.email))


if __name__ == "__main__":
    main()
