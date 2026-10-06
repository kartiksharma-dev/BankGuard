from dataclasses import dataclass, field


@dataclass
class CustomerProfile:
    customer_id: str
    usual_device: str
    usual_location: str

    account_balance: float = 100000.0

    transaction_count: int = 0
    transaction_history: list[float] = field(default_factory=list)

    step: int = 0

    def record_transaction(self, amount: float) -> None:
        self.transaction_count += 1
        self.transaction_history.append(amount)

        self.account_balance -= amount

        self.step += 1


@dataclass
class DestinationAccount:
    account_id: str
    balance: float = 50000.0

    def receive_transaction(self, amount: float) -> None:
        self.balance += amount