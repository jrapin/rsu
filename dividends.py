import dataclasses
import typing as tp
import datetime
from pathlib import Path
import argparse
import datetime
import json
# equity awards
# afficher l'historique
# dl
from rsu import convert_schwab_float_format, ExchangeRateData


@dataclasses.dataclass
class Dividend:
    date: datetime.datetime
    amount_usd: float

    @classmethod
    def from_line(cls, line: dict[str, tp.Any]):
        date_schwab_format = "%m/%d/%Y"
        date = datetime.datetime.strptime(line["Date"], date_schwab_format)
        # We will check at the end that the sum of the shares in the transactions is equal to the quantity in the sale event
        # same for the total sale amount
        amount_usd = convert_schwab_float_format(line["Amount"])
        return cls(date=date, amount_usd=amount_usd)

    def process(self, xrate: ExchangeRateData) -> str:
        euro_dollar = xrate.get_euro_dollar_rate(self.date)
        strings = [f"{self.date}: ${self.amount_usd} ({euro_dollar:.2f}$/€)"]
        amount = self.amount_usd / euro_dollar
        strings += [f"Dividende (IK):\t{amount:.2f}€"]
        IK = amount
        rates = dict(IL=12.8, PQ=9.2, PV=0.5, PG=7.5)
        vals = {x: round(IK * rate / 100, 2) for x, rate in rates.items()}
        vals["PF"] = vals["PV"] + vals["PQ"]
        vals["PT"] = vals["PF"] + vals["PG"]
        vals["QR"] = vals["PT"] + vals["IL"]
        vals["paiement"] = vals["QR"]
        names = ["paiement", "IL", "PQ", "PV", "PF", "PG", "PT", "QR"]
        for name in names:
            strings+= [f"{name}\t{vals[name]:.2f}".replace(".", ",")]
        return "\n".join(strings)








def load_dividends(schwab_json: Path):
    """
    Load and parse transaction details from a Schwab JSON file for a specific year.

    Args:
        schwab_json (str): The path to the Schwab JSON file.
        year (int): The year for which to retrieve the transactions details.

    Returns:
        list: A list of TransactionDetails objects containing the parsed transaction details.

    """
    return dividends


def process(schwab_json: Path) -> None:
    date_schwab_format = "%m/%d/%Y"
    with schwab_json.open() as jfile:
        schwab_data = json.load(jfile)
    dividends = [Dividend.from_line(d) for d in schwab_data["Transactions"] if d["Action"] == "Dividend"]
    dividends.sort(key=lambda d: d.date)
    xrate_fp = schwab_json.with_name("exchange_rates.csv")
    xrate = ExchangeRateData(xrate_fp)
    out = []
    for d in dividends:
        out.append(d.process(xrate=xrate))
    summ = "\n\n".join(out)
    schwab_json.with_name("summary-dividendes.txt").write_text(summ)
    print(summ)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filepath')
    args = parser.parse_args()
    filepath = Path(args.filepath).absolute()
    process(filepath)
