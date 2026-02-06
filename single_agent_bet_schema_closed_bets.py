import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "6e7d4874d1af75c52046dd2211eda7bb"
AGENT_ADDRESS = "0xb5494f8044079c29fd5d2f78ee270224b04fcdde"
DAYS_TO_SCAN = 30  
WEI_IN_ETH = 10**18

# ENDPOINT
SUBGRAPH_TRADES = f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/9fUVQpFwzpdWS9bq5WkAnmKbNNcoBwatMR4yZq81pbbz"

def run_query(query, variables):
    try:
        response = requests.post(SUBGRAPH_TRADES, json={'query': query, 'variables': variables})
        if response.status_code == 200: return response.json()
        print(f"Error: {response.status_code}")
    except Exception as e: print(f"Connection Error: {e}")
    return None

def fetch_trade_history():
    print(f"fetching trades for {AGENT_ADDRESS} (Last {DAYS_TO_SCAN} days)...")
    
    start_date = datetime.now() - timedelta(days=DAYS_TO_SCAN)
    min_timestamp = int(start_date.timestamp())
    all_trades = []
    last_timestamp = int(datetime.now().timestamp())
    
    while True:
        query = """
        query GetHistory($user: String!, $maxTime: BigInt!, $minTime: BigInt!) {
            fpmmTrades(
                where: { creator: $user, creationTimestamp_lt: $maxTime, creationTimestamp_gt: $minTime }
                first: 1000
                orderBy: creationTimestamp
                orderDirection: desc
            ) {
                id                  
                creationTimestamp
                type
                collateralAmount
                feeAmount
                outcomeTokensTraded
                outcomeIndex
                fpmm { 
                    id
                    currentAnswer 
                    outcomes
                    question { title } 
                }
            }
        }
        """
        variables = {
            "user": AGENT_ADDRESS.lower(),
            "maxTime": str(last_timestamp),
            "minTime": str(min_timestamp)
        }
        
        data = run_query(query, variables)
        if not data or "data" not in data: break
        
        trades = data["data"].get("fpmmTrades", [])
        if not trades: break
        
        all_trades.extend(trades)
        last_timestamp = trades[-1]["creationTimestamp"]
        
        if len(trades) < 1000: break
    
    return all_trades

def format_outcome_label(fpmm, index):
    try:
        if fpmm.get("outcomes") and len(fpmm["outcomes"]) > int(index):
            return fpmm["outcomes"][int(index)]
        return str(index)
    except:
        return str(index)

def process_trades(trades):
    # Adjust column widths
    print(f"\n{'DATE':<10} | {'TYPE':<4} | {'BET (PICK)':<15} | {'RESULT':<8} | {'COST':<8} | {'REVENUE':<8} | {'ROI':<8} | {'TRADE ID (Full)'}")
    print("-" * 130)

    total_cost = 0.0
    total_rev = 0.0

    for t in trades:
        # We keep the full ID available
        full_id = t['id']
        
        date_str = datetime.fromtimestamp(int(t["creationTimestamp"])).strftime('%Y-%m-%d')
        market = t.get("fpmm")
        
        amount = float(t["collateralAmount"]) / WEI_IN_ETH
        fees = float(t["feeAmount"]) / WEI_IN_ETH
        tokens = float(t["outcomeTokensTraded"]) / WEI_IN_ETH
        
        cost = 0.0
        revenue = 0.0
        roi_str = "-"
        result_str = "OPEN"
        pick_label = format_outcome_label(market, t["outcomeIndex"])

        if t["type"] == "Buy":
            cost = amount + fees
            # REMOVED: total_cost += cost (Moved inside resolution check)
            
            if market and market.get("currentAnswer") is not None:
                try:
                    winning_index = int(market["currentAnswer"], 16)
                    
                    # Basic check for valid answer (Omen uses huge hex for pending)
                    if winning_index > 1000:
                         result_str = "PENDING"
                    else:
                        picked_index = int(t["outcomeIndex"])
                        
                        # Only add cost if we have a valid resolution
                        total_cost += cost
                        
                        if winning_index == picked_index:
                            result_str = "WIN"
                            revenue = tokens
                            total_rev += revenue
                            roi = ((revenue - cost) / cost) * 100
                            roi_str = f"{roi:>.0f}%"
                        else:
                            result_str = "LOSS"
                            revenue = 0.0
                            roi_str = "-100%"
                except:
                    result_str = "ERR"
            else:
                result_str = "PENDING"

        elif t["type"] == "Sell":
            cost = 0.0
            revenue = amount
            total_rev += revenue
            result_str = "EXIT"
            roi_str = "N/A"

        # To keep the table clean, I display the start and unique end of the ID
        display_id = full_id[:10] + "..." + full_id[-8:]
        
        print(f"{date_str:<10} | {t['type']:<4} | {pick_label:<15} | {result_str:<8} | ${cost:<8.2f} | ${revenue:<8.2f} | {roi_str:<8} | {display_id}")

    print("-" * 130)
    print(f"REALIZED TOTALS: {'':<32} | ${total_cost:<8.2f} | ${total_rev:<8.2f}")
    if total_cost > 0:
        total_roi = ((total_rev - total_cost) / total_cost) * 100
        print(f"REALIZED AGGREGATE ROI: {total_roi:.2f}%")

if __name__ == "__main__":
    trades = fetch_trade_history()
    if trades:
        process_trades(trades)
    else:
        print("No trades found.")