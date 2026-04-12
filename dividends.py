import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
import pandas as pd

from rsu import ExchangeRateData


@dataclass
class TransactionDetails:
    # Transaction Date
    date: datetime
    # Total dividend amount in USD
    amount_usd: float

@dataclass
class TaxRates:
    # US tax rate on dividends (15% of base USD)
    impots_usa: float
    # Income tax rate in EUR (12.8% of base EUR)
    impots_revenu: float
    # CSG rate (9.2% of base EUR before 2025, then 10.6% since 2025)
    CSG: float
    # CRDS rate (0.5% of base EUR)
    CRDS: float
    # Solidarity tax rate (7.5% of base EUR)
    prelevement_solidarite: float

@dataclass
class TransactionDetailsProcessed:
    # Transaction Date
    date: datetime
    # Exchange rate EUR -> USD for the transaction date
    exchange_rate: float
    # Total dividend amount in USD
    base_usd: float
    # Total dividend amount in EUR
    base_eur: int
    # Withholding tax in USD
    impots_usa_usd: float
    # Withholding tax in EUR
    impots_usa_eur: int
    # Income tax in EUR (12.8% of base EUR)
    impots_Revenu_IL: int
    # CSG in EUR (9.2% of base EUR)
    CSG_PQ: int
    # CRDS in EUR (0.5% of base EUR)
    CRDS_PV: int
    # Subtotal CSG + CRDS in EUR
    sous_total_CSG_CRDS_PF: int
    # Solidarity tax in EUR (7.5% of base EUR)
    prelevement_solidarite_PG: int
    # Total social contributions and taxes in EUR
    total_contributions_prelevements_sociaux_PT: int
    # Total taxes in EUR
    total_impots_QR: int
    # Net amount received in EUR
    net_percu: int


def get_tax_rates(year: int) -> TaxRates:
    # For simplicity, we only support the years after 2018, with a flat tax rate on dividends
    if year < 2018:
        raise ValueError("Only the year >=2018 is supported for now")
    elif year <= 2025:
        # Before 2026, CSG is at 17.2%, and income tax is at 12.8% (so 30% flat tax rate)
        return TaxRates(
            impots_usa=0.15,
            impots_revenu=0.128,
            CSG=0.092,
            CRDS=0.005,
            prelevement_solidarite=0.075,
        )
    else:
        # Since 2026, CSG is at 18.6%, and income tax is still at 12.8% (so 31.4% flat tax rate)
        return TaxRates(
            impots_usa=0.15,
            impots_revenu=0.128,
            CSG=0.106,
            CRDS=0.005,
            prelevement_solidarite=0.075,
        )

def convert_schwab_float_format(s: str) -> float:
    # Format is $XXX,XXX.XX
    return float(s.replace("$", "").replace(",", ""))


def load_transactions_details(schwab_json: str, year: int):
    """
    Load and parse transaction details from a Schwab JSON file for a specific year.

    Args:
        schwab_json (str): The path to the Schwab JSON file.
        year (int): The year for which to retrieve the transactions details.

    Returns:
        list: A list of TransactionDetails objects containing the parsed transaction details.

    """
    with open(schwab_json) as jfile:
        schwab_data = json.load(jfile)
    dividends = [d for d in schwab_data["Transactions"] if d["Action"] == "Dividend"]
    transactions_details = []
    date_schwab_format = "%m/%d/%Y"
    for dividend in dividends:
        date = datetime.strptime(dividend["Date"], date_schwab_format)
        if date.year != year:
            continue
        amount_usd = convert_schwab_float_format(dividend["Amount"])
        transactions_details.append(TransactionDetails(date=date, amount_usd=amount_usd))
    return transactions_details



def process_transaction(
    src: TransactionDetails, change_data: ExchangeRateData, tax_rates: TaxRates
) -> TransactionDetailsProcessed:
    """
    Process a transaction and calculate various details related to the transaction.

    Args:
        src (TransactionDetails): The transaction details.
        exchange_rate_csv (str): The path to the CSV file containing exchange rate data.

    Returns:
        TransactionDetailsProcessed: The processed transaction details.

    Raises:
        FileNotFoundError: If the exchange rate CSV file is not found.
    """
    exchange_rate = change_data.get_euro_dollar_rate(src.date)
    base_eur = round(src.amount_usd / exchange_rate)
    
    base_usd=src.amount_usd
    base_eur=round(src.amount_usd / exchange_rate)
    impots_usa_usd=base_usd * tax_rates.impots_usa
    impots_usa_eur=round(impots_usa_usd/ exchange_rate)
    impots_Revenu_IL=round(base_eur * tax_rates.impots_revenu)
    CSG_PQ=round(base_eur * tax_rates.CSG)
    CRDS_PV=round(base_eur * tax_rates.CRDS)
    sous_total_CSG_CRDS_PF=CSG_PQ + CRDS_PV
    prelevement_solidarite_PG=round(base_eur * tax_rates.prelevement_solidarite)
    total_contributions_prelevements_sociaux_PT=sous_total_CSG_CRDS_PF + prelevement_solidarite_PG
    total_impots_QR = impots_Revenu_IL + total_contributions_prelevements_sociaux_PT
    net_percu=base_eur - impots_usa_eur
        
    return TransactionDetailsProcessed(
        date=src.date,
        exchange_rate=exchange_rate,
        base_usd=src.amount_usd,
        base_eur=base_eur,
        impots_usa_usd=impots_usa_usd,
        impots_usa_eur=impots_usa_eur,
        impots_Revenu_IL=impots_Revenu_IL,
        CSG_PQ=CSG_PQ,
        CRDS_PV=CRDS_PV,
        sous_total_CSG_CRDS_PF=sous_total_CSG_CRDS_PF,
        prelevement_solidarite_PG=prelevement_solidarite_PG,
        total_contributions_prelevements_sociaux_PT=total_contributions_prelevements_sociaux_PT,
        total_impots_QR=total_impots_QR,
        net_percu=net_percu,
    )


def process_all_transactions(transactions: list, change_data: ExchangeRateData, tax_rates: TaxRates) -> list:
    """
    Process a list of transactions and calculate various details for each transaction.

    Args:
        transactions (list): A list of TransactionDetails objects.
        change_data (ExchangeRateData): The exchange rate data.

    Returns:
        list: A list of TransactionDetailsProcessed objects containing the processed transaction details.
    """
    return [process_transaction(tr, change_data, tax_rates) for tr in transactions]


def write_output_csv(trs: List[TransactionDetailsProcessed], csv_filename: Path):
    trs.sort(key=lambda x: x.date)
    df = pd.DataFrame(trs)        
    column_mapping = {
        "date": "Date de paiement",
        "exchange_rate": "Taux de change EUR USD",
        "base_usd": "Montant brut (USD)",
        "base_eur": "Montant brut (EUR)",
        "impots_usa_usd": "Retenue a la source USA (15%) (USD)",
        "impots_usa_eur": "Retenue a la source USA (15%) (EUR)",
        "impots_Revenu_IL": "[IL] Impot sur le revenu (12.8%) (EUR)",
        "CSG_PQ": "[PQ] CSG (9.2%) (EUR)",
        "CRDS_PV": "[PV] CRDS (0.5%) (EUR)",
        "sous_total_CSG_CRDS_PF": "[PF] CSG + CRDS (EUR)",
        "prelevement_solidarite_PG": "[PG] Prelevement de solidarite (7.5%) (EUR)",
        "total_contributions_prelevements_sociaux_PT": "[PT] Total contributions et prelevements sociaux (EUR)",
        "total_impots_QR": "[QR] Total impots (EUR)",
        "net_percu": "Net percu (EUR)",
    }
    # Rename the columns using the mapping
    df = df.rename(columns=column_mapping)
    # Use this format so that Google Sheets can parse the number correctly
    df.to_csv(csv_filename, sep="\t", float_format="%.4f", decimal=",")



@click.command()
@click.option(
    "--schwab_json",
    type=click.Path(exists=True, path_type=Path),
    help="Input JSON file containing the Schwab RSU data",
)
@click.option("--year", type=int, help="Year to process the data for")
@click.option(
    "--output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory path",
)
@click.option(
    "--eur_xr_csv",
    default=None,
    type=click.Path(path_type=Path),
    help="CSV file containing the EUR to USD exchange rate data. Will be downloaded if not provided.",
)
def main(
    schwab_json: Path,
    year: int,
    output_dir: Path,
    eur_xr_csv: Optional[Path],
):
    xr_data = ExchangeRateData(eur_xr_csv)
    tax_rates = get_tax_rates(year)
    transactions = load_transactions_details(schwab_json, year)
    processed = process_all_transactions(transactions, xr_data, tax_rates)
    output_dir.mkdir(exist_ok=True, parents=True)
    write_output_csv(processed, output_dir / f"dividends_{year}.csv")


if __name__ == "__main__":
    main()
