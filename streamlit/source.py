import pandas as pd
import numpy as np

class Strategy_A:
    def __init__(self,
                 df=None,
                 paths: list[str] = None,
                 start_balance: float = 100.0,
                 fee_rate: float = 0.00065,
                 tp_pct: float = 0.0025,
                 sl_pct: float = 0.0015,
                 window: int = 15,
                 long_th: float = 0.22,
                 short_th: float = -0.22,
                 max_spread: float = 0.07,
                 risk_pct: float = 0.015,
                 min_imb_duration: int = 4,
                 use_dynamic_exits: bool = True,
                 volatility_window: int = 50,
                 act_on_price_change: float = 0.0006,
                 miniburst_window: int = 7,
                 miniburst_multiplier: float = 2.2,
                 local_extremum_lookback: int = 5):
        """
        This strategy improves selectivity by only opening positions when:
          - Imbalance is very strong (configurable threshold, higher default)
          - The imbalance has lasted for several candles (confirmation)
          - AND one of the following *matters*:
              - A price miniburst with the same direction as the imbalance is occurring (momentum + excess volume)
              - We are at/near a local price extremum, suggesting a potential reversal
              - The spread/volatility are in the trader's favor
        """

        self.start_balance = float(start_balance)
        self.fee_rate = float(fee_rate)
        self.tp_pct = float(tp_pct)
        self.sl_pct = float(sl_pct)
        self.window = int(window)
        self.long_th = float(long_th)   # Make thresholds higher than before
        self.short_th = float(short_th)
        self.max_spread = float(max_spread)
        self.risk_pct = float(risk_pct)
        self.min_imb_duration = int(min_imb_duration)
        self.use_dynamic_exits = use_dynamic_exits
        self.volatility_window = int(volatility_window)

        # New: miniburst check and local extremum/selectivity params
        self.act_on_price_change = float(act_on_price_change)
        self.miniburst_window = int(miniburst_window)
        self.miniburst_multiplier = float(miniburst_multiplier)
        self.local_extremum_lookback = int(local_extremum_lookback)

        if df is not None:
            self.df = df.copy()
            if 'ts' in self.df.columns:
                if not pd.api.types.is_datetime64_any_dtype(self.df['ts']):
                    self.df['ts'] = pd.to_datetime(self.df['ts'])
        elif paths:
            dfs = []
            for p in paths:
                dfs.append(pd.read_csv(p, parse_dates=["ts"]))
            self.df = pd.concat(dfs, ignore_index=True).sort_values("ts").reset_index(drop=True)
        else:
            raise ValueError("Either df or paths must be provided")

        for c in ["best_bid_price", "best_bid_size", "best_ask_price", "best_ask_size"]:
            if c in self.df.columns:
                self.df[c] = pd.to_numeric(self.df[c], errors="coerce")

    def engine(self) -> pd.DataFrame:
        df = self.df.copy()
        # Reset index to ensure consistent integer-based indexing
        df = df.reset_index(drop=True)

        df["spread"] = df["best_ask_price"] - df["best_bid_price"]
        df["mid_price"] = (df["best_bid_price"] + df["best_ask_price"]) / 2
        df["spread_pct"] = df["spread"] / df["mid_price"]

        denom = (df["best_bid_size"] + df["best_ask_size"]).replace(0, pd.NA)
        df["l1_imbalance"] = (df["best_bid_size"] - df["best_ask_size"]) / denom
        df["l1_imb_smooth"] = df["l1_imbalance"].rolling(self.window, min_periods=1).mean()
        df["l1_imb_momentum"] = df["l1_imb_smooth"].diff(3)
        
        denom2 = (df["best_bid_size"] + df["best_ask_size"]).replace(0, pd.NA)
        df["microprice"] = (
            df["best_bid_price"] * df["best_ask_size"] +
            df["best_ask_price"] * df["best_bid_size"]
        ) / denom2
        df["micro_bias"] = df["microprice"] - df["mid_price"]
        
        df["returns"] = df["mid_price"].pct_change()
        df["volatility"] = df["returns"].rolling(self.volatility_window, min_periods=10).std()
        
        spread_ma = df["spread_pct"].rolling(20, min_periods=1).mean()
        df["spread_filter"] = df["spread_pct"] < (spread_ma * 1.5)

        # Mini-burst detection: large single candle movement vs recent normal
        abs_rets = df["mid_price"].pct_change().abs()
        burst_ma = abs_rets.rolling(self.miniburst_window, min_periods=2).mean()
        df["price_burst_up"] = (
            (df["mid_price"].pct_change() > self.act_on_price_change)
            & (abs_rets > burst_ma * self.miniburst_multiplier)
        )
        df["price_burst_down"] = (
            (df["mid_price"].pct_change() < -self.act_on_price_change)
            & (abs_rets > burst_ma * self.miniburst_multiplier)
        )

        # Local Extremum: are we at a local max/min compared to history? (± local_extremum_lookback)
        # True if current price is biggest/smallest in a window (lookback)
        df["is_local_max"] = df["mid_price"] == df["mid_price"].rolling(self.local_extremum_lookback, min_periods=1).max()
        df["is_local_min"] = df["mid_price"] == df["mid_price"].rolling(self.local_extremum_lookback, min_periods=1).min()

        # Improved signal calculation: only open position when ALL of:
        # 1) Imbalance is strong
        # 2) Imbalance is persistent for min duration
        # 3) Entry only if (single candle miniburst OR local extremum) suggests regime change or impulse
        # 4) Spread filter, micro-bias, and momentum as further confirmation

        df["raw_signal"] = 0

        # Candidate long: very strong positive imbalance and confirmation
        df.loc[
            (df["l1_imb_smooth"] > self.long_th)
            & (df["spread"] < self.max_spread)
            & (df["spread_filter"])
            & (df["micro_bias"] > 0)
            & (df["l1_imb_momentum"] > -0.04)
            &
            (
                df["price_burst_up"] | df["is_local_min"]
            ),
            "raw_signal"
        ] = 1

        # Candidate short: very strong negative imbalance and confirmation
        df.loc[
            (df["l1_imb_smooth"] < self.short_th)
            & (df["spread"] < self.max_spread)
            & (df["spread_filter"])
            & (df["micro_bias"] < 0)
            & (df["l1_imb_momentum"] < 0.04)
            &
            (
                df["price_burst_down"] | df["is_local_max"]
            ),
            "raw_signal"
        ] = -1

        # Signal persistence filter (avoid fleeting signals) -- only if *all* of previous N raw are same
        df["final_signal"] = 0
        if len(df) > self.min_imb_duration:
            for i in range(self.min_imb_duration, len(df)):
                window_signals = df["raw_signal"].iloc[i-self.min_imb_duration:i+1]
                if (window_signals == 1).all():
                    df.loc[i, "final_signal"] = 1
                elif (window_signals == -1).all():
                    df.loc[i, "final_signal"] = -1

        # We want to see only *fresh* signals -- open position only if didn't have same signal last bar
        df["final_signal_trigger"] = (df["final_signal"].diff().fillna(0) != 0) & (df["final_signal"] != 0)
        df.loc[~df["final_signal_trigger"], "final_signal"] = 0  # Only trigger at regime change

        return df

    def backtest(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = self.engine()
        df = df.dropna(subset=["ts", "mid_price", "final_signal", "spread"]).copy()
        df = df.sort_values("ts").reset_index(drop=True)

        equity = self.start_balance
        peak_equity = equity

        position = None
        trades = []
        trade_id = 0

        for idx, row in df.iterrows():
            ts = row["ts"]
            price = float(row["mid_price"])
            vol = float(row.get("volatility", 0.001))

            # ENTRY
            if position is None:
                sig = int(row["final_signal"])
                if sig == 0:
                    continue

                side = "LONG" if sig == 1 else "SHORT"
                entry = price

                # Dynamic TP/SL based on volatility
                if self.use_dynamic_exits and vol > 0:
                    vol_multiplier = np.clip(vol / 0.001, 1.0, 3.0)
                    tp_pct = self.tp_pct * vol_multiplier
                    sl_pct = self.sl_pct * vol_multiplier
                else:
                    tp_pct = self.tp_pct
                    sl_pct = self.sl_pct

                sl_price = entry * (1 - sl_pct) if side == "LONG" else entry * (1 + sl_pct)
                tp_price = entry * (1 + tp_pct) if side == "LONG" else entry * (1 - tp_pct)
                
                risk_usd = equity * self.risk_pct
                sl_dist = abs(entry - sl_price)
                if sl_dist <= 0:
                    continue

                qty = risk_usd / sl_dist

                position = {
                    "id": trade_id,
                    "side": side,
                    "ts_entry": ts,
                    "entry": entry,
                    "qty": qty,
                    "equity_entry": equity,
                    "tp_price": tp_price,
                    "sl_price": sl_price,
                    "tp_pct": tp_pct,
                    "sl_pct": sl_pct
                }
                trade_id += 1
                continue

            # EXIT
            side = position["side"]
            entry = position["entry"]
            qty = position["qty"]
            tp = position["tp_price"]
            sl = position["sl_price"]

            hit_tp = price >= tp if side == "LONG" else price <= tp
            hit_sl = price <= sl if side == "LONG" else price >= sl

            if not (hit_tp or hit_sl):
                continue

            exit_price = tp if hit_tp else sl
            reason = "TP" if hit_tp else "SL"

            notional_entry = entry * qty
            notional_exit = exit_price * qty

            fees_usd = (notional_entry + notional_exit) * self.fee_rate

            gross_pnl = (exit_price - entry) * qty if side == "LONG" else (entry - exit_price) * qty
            net_pnl = gross_pnl - fees_usd

            equity = equity + net_pnl
            peak_equity = max(peak_equity, equity)
            dd = (equity - peak_equity)

            trades.append({
                "trade_id": position["id"],
                "side": side,
                "ts_entry": position["ts_entry"],
                "ts_exit": ts,
                "entry": entry,
                "exit": exit_price,
                "tp_price": tp,
                "sl_price": sl,
                "qty": qty,
                "reason": reason,
                "gross_pnl_usd": gross_pnl,
                "fees_usd": fees_usd,
                "net_pnl_usd": net_pnl,
                "equity_after": equity,
                "drawdown_usd": dd
            })

            position = None

        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            trades_df["cum_pnl_usd"] = trades_df["net_pnl_usd"].cumsum()
            trades_df["equity_curve"] = self.start_balance + trades_df["cum_pnl_usd"]
        else:
            # Ensure empty DataFrame has expected columns for consistency
            trades_df = pd.DataFrame(columns=[
                "trade_id", "side", "ts_entry", "ts_exit", "entry", "exit", 
                "tp_price", "sl_price", "qty", "reason", "gross_pnl_usd", 
                "fees_usd", "net_pnl_usd", "equity_after", "drawdown_usd"
            ])

        return df, trades_df

    @staticmethod
    def compute_stats(trades_df: pd.DataFrame, start_balance: float) -> dict:
        if trades_df is None or trades_df.empty:
            return {}

        net = trades_df["net_pnl_usd"]
        wins = net[net > 0]
        losses = net[net < 0]

        win_rate = float((net > 0).mean())
        total_net = float(net.sum())
        profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) else float("inf")
        avg_trade = float(net.mean())

        sharpe = float(net.mean() / net.std()) if net.std() > 0 else 0

        eq = trades_df["equity_curve"]
        running_max = eq.cummax()
        dd = eq - running_max
        max_dd = float(dd.min())
        max_dd_pct = float((dd / running_max).min()) if running_max.max() > 0 else 0

        roi = total_net / start_balance

        tp_count = int((trades_df["reason"] == "TP").sum())
        sl_count = int((trades_df["reason"] == "SL").sum())

        return {
            "Trades": int(len(trades_df)),
            "Win rate": win_rate,
            "Profit factor": profit_factor,
            "Total net PnL (USD)": total_net,
            "ROI": roi,
            "Avg net per trade (USD)": avg_trade,
            "Max drawdown (USD)": max_dd,
            "Max drawdown (%)": max_dd_pct,
            "Sharpe": sharpe,
            "TP exits": tp_count,
            "SL exits": sl_count
        }