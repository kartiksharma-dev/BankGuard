import argparse
import time

from simulator.generator import create_customer, generate_transaction
from simulator.scenarios import TransactionScenario


def run_simulator(
    transactions_per_second: int = 1,
    duration_seconds: int = 10,
):
    customer = create_customer("C1029")

    interval = 1 / transactions_per_second

    start_time = time.time()

    while time.time() - start_time < duration_seconds:
        transaction = generate_transaction(
            scenario=TransactionScenario.NORMAL,
            customer=customer,
        )

        print(transaction)

        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BankGuard Transaction Simulator"
    )

    parser.add_argument(
        "--rate",
        type=int,
        default=1,
        help="Transactions per second",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Simulation duration in seconds",
    )

    args = parser.parse_args()

    run_simulator(
        transactions_per_second=args.rate,
        duration_seconds=args.duration,
    )