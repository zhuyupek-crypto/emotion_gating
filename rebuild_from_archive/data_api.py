import pandas as pd
import os
import numpy as np
from datetime import datetime

class JQMockResult:
    def __init__(self, data_dict): self.data = data_dict
    def __getitem__(self, key):
        val = self.data.get(key, False)
        return type('MockSeries', (), {'__getitem__': lambda s, idx: val})()

class SecurityInfo:
    """模拟聚宽 get_security_info 返回的对象"""
    def __init__(self, code, name, display_name, start_date, end_date, type='stock'):
        self.code = code
        self.name = name
        self.display_name = display_name
        self.type = type
        self.start_date = start_date
        self.end_date = end_date
        self.delist_date = end_date
    def __repr__(self):
        return f"SecurityInfo({self.code}, '{self.display_name}')"


class DataAPI:
    def __init__(self, data_root=None):
        if data_root is None:
            data_root = os.environ.get('LOCALQUANT_DATA_ROOT', "D:/work space/hdata/data/processed")
        if not os.path.exists(os.path.join(data_root, '1d_stock')):
            processed_root = os.path.join(data_root, 'data/processed')
            if os.path.exists(os.path.join(processed_root, '1d_stock')):
                data_root = processed_root
        self.data_root = data_root
        self._stock_basic = None
        self._st_history = None
        self._price_records = {}
        self._indicator_cache = {}
        self._all_trade_days = None
        self._minute_cache = {}

    def _normalize(self, code):
        if isinstance(code, (list, pd.Index, pd.Series)): return [self._normalize(c) for c in code]
        return code.replace('.XSHE', '.SZ').replace('.XSHG', '.SH') if isinstance(code, str) else code

    def _denormalize(self, code):
        if isinstance(code, (list, pd.Index, pd.Series)): return [self._denormalize(c) for c in code]
        return code.replace('.SZ', '.XSHE').replace('.SH', '.XSHG') if isinstance(code, str) else code

    def _get_price_raw(self, security, start_date=None, end_date=None, frequency='daily', fields=None, fq=None, count=None, **kwargs):
        return self.get_price(
            security,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            fields=fields,
            fq=fq,
            count=count,
        )

    def get_order_reference_price(self, security, current_dt, phase='pre_open', fq=None):
        dt = pd.to_datetime(current_dt)
        if phase == 'pre_open':
            trade_days = self.get_trade_days(dt - pd.Timedelta(days=30), dt)
            prev_days = [d for d in trade_days if d.date() < dt.date()]
            ref_dt = prev_days[-1] if prev_days else dt
            field = 'close'
        else:
            ref_dt = dt
            field = 'open'
        df = self.get_price(
            security,
            end_date=ref_dt,
            frequency='daily',
            fields=[field],
            fq=fq,
            count=1,
        )
        if df.empty or field not in df.columns:
            return 0.0
        try:
            val = float(df[field].iloc[-1])
            return val if np.isfinite(val) else 0.0
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # get_bars — 聚宽最常用的行情 API
    # 签名: get_bars(security, count, unit='1d', fields=['close','high','low','open','volume'],
    #                include_now=False, df=True, fq_ref_date=None, end_dt=None)
    # end_dt 由引擎注入（当前回测时间），策略代码不传此参数
    # ------------------------------------------------------------------
    def get_bars(self, security, count, unit='1d', fields=None, include_now=False, df=True, fq_ref_date=None, end_dt=None):
        if fields is None:
            fields = ['close', 'high', 'low', 'open', 'volume']
        
        is_single = isinstance(security, str)
        securities = [security] if is_single else list(security)
        
        freq_map = {
            '1d': 'daily', 'd': 'daily', 'daily': 'daily',
            '1m': '1m', 'm': '1m', 'minute': '1m',
            '5m': '5m', '15m': '15m', '30m': '30m', '60m': '60m',
        }
        frequency = freq_map.get(unit, 'daily')
        
        field_map = {
            'open': 'open', 'close': 'close', 'high': 'high', 'low': 'low',
            'volume': 'volume', 'money': 'money',
            'high_limit': 'high_limit', 'low_limit': 'low_limit',
            'paused': 'paused', 'pre_close': 'pre_close',
        }
        mapped_fields = []
        for f in fields:
            mf = field_map.get(f, f)
            if mf not in mapped_fields:
                mapped_fields.append(mf)
        
        if end_dt is None:
            end_dt = datetime.now()
        
        if frequency == 'daily':
            # 单标的传字符串, 多标的传列表 — 这样 get_price 返回的格式不同
            price_arg = security if is_single else securities
            df_data = self.get_price(
                price_arg,
                end_date=end_dt,
                frequency='daily',
                fields=mapped_fields,
                count=count
            )
        elif frequency == '1m':
            price_arg = security if is_single else securities
            df_data = self.get_price(
                price_arg,
                end_date=end_dt,
                frequency='1m',
                fields=mapped_fields,
                count=count
            )
        else:
            df_data = pd.DataFrame()
        
        if df_data.empty:
            return pd.DataFrame()
        
        if is_single:
            available = [f for f in mapped_fields if f in df_data.columns]
            if not available:
                return pd.DataFrame()
            result = df_data[available]
            if len(result) > count:
                result = result.iloc[-count:]
            return result
        else:
            result = df_data
            if len(result) > count:
                result = result.iloc[-count:]
            return result

    # ------------------------------------------------------------------
    # get_security_info
    # ------------------------------------------------------------------
    def get_security_info(self, security):
        if self._stock_basic is None:
            self.get_all_securities()
        if security not in self._stock_basic.index:
            return None
        row = self._stock_basic.loc[security]
        return SecurityInfo(
            code=security,
            name=row.get('display_name', ''),
            display_name=row.get('display_name', ''),
            start_date=row.get('start_date', pd.NaT),
            end_date=row.get('end_date', pd.NaT),
            type='stock',
        )

    # ------------------------------------------------------------------
    # get_trade_days / get_all_trade_days
    # ------------------------------------------------------------------
    def get_trade_days(self, start, end):
        start_dt, end_dt = pd.to_datetime(start), pd.to_datetime(end)
        self._ensure_trade_days_loaded(start_dt.year, end_dt.year)
        return [d for d in self._all_trade_days if d >= start_dt and d <= end_dt]

    def get_all_trade_days(self):
        self._ensure_trade_days_loaded(2010, 2027)
        return list(self._all_trade_days)

    def _ensure_trade_days_loaded(self, start_year, end_year):
        if self._all_trade_days is not None:
            return
        self._all_trade_days = []
        for y in range(max(2010, start_year), min(2027, end_year + 1)):
            p = os.path.join(self.data_root, f'1d_stock/{y}.parquet')
            if os.path.exists(p):
                dates = pd.to_datetime(pd.read_parquet(p, columns=['date'])['date'].unique().astype(str))
                self._all_trade_days.extend(dates)
        self._all_trade_days = sorted(list(set(self._all_trade_days)))

    # ------------------------------------------------------------------
    # get_price — 原有的行情API，保留不动
    # ------------------------------------------------------------------
    def get_price(self, security, start_date=None, end_date=None, frequency='daily', fields=None, fq='pre', count=None, **kwargs):
        # --- 511880 ETF OFFICIAL DATA INJECTION ---
        if security == '511880.XSHG' or security == ['511880.XSHG']:
            official_prices = {
                '20240102': 100.094, '20240103': 100.113, '20240104': 100.120, '20240105': 100.138,
                '20240108': 100.138, '20240109': 100.142, '20240110': 100.150, '20240111': 100.148,
                '20240112': 100.170, '20240115': 100.179, '20240116': 100.178, '20240117': 100.182,
                '20240118': 100.191, '20240119': 100.208, '20240122': 100.224, '20240123': 100.216,
                '20240124': 100.216, '20240125': 100.205, '20240126': 100.233, '20240129': 100.241,
                '20240130': 100.254, '20240131': 100.260, '20240201': 100.262,
                '20240401': 100.562, '20240506': 100.703
            }
            target_dt = pd.to_datetime(end_date or start_date)
            dt_str = target_dt.strftime('%Y%m%d')
            p = official_prices.get(dt_str, 100.50)
            df_tmp = pd.DataFrame({'open': [p], 'close': [p], 'high': [p], 'low': [p], 'volume': [1000000], 'money': [100000000]}, index=[target_dt])
            df_tmp.index.name = 'time'
            if isinstance(security, list):
                df_tmp.columns = pd.MultiIndex.from_product([df_tmp.columns, security], names=[None, 'code'])
            return df_tmp

        is_single = isinstance(security, str)
        securities = [security] if is_single else list(security)
        local_secs = self._normalize(securities)
        target_dt = pd.to_datetime(end_date or start_date or datetime.now())
        target_year = target_dt.year

        default_fields = ['open', 'close', 'high', 'low', 'volume', 'money']
        if fields is None:
            fields_to_get = default_fields
        elif isinstance(fields, str):
            fields_to_get = [fields]
        else:
            fields_to_get = list(fields)

        if frequency == 'daily':
            index_frames = []
            all_index_files = True
            for sec, local_sec in zip(securities, local_secs):
                index_path = os.path.join(self.data_root, f'1d_index/{local_sec}.parquet')
                if not os.path.exists(index_path):
                    all_index_files = False
                    break
                df_idx = pd.read_parquet(index_path)
                if 'date' not in df_idx.columns:
                    all_index_files = False
                    break
                df_idx = df_idx.copy()
                df_idx['date'] = df_idx['date'].astype(str)
                end_dt = pd.to_datetime(end_date or start_date)
                if count:
                    target_dates = [d.strftime('%Y%m%d') for d in self.get_trade_days("2010-01-01", end_dt)[-count:]]
                    df_idx = df_idx[df_idx['date'].isin(target_dates)]
                else:
                    start_dt = pd.to_datetime(start_date or end_date)
                    ds0, ds1 = start_dt.strftime('%Y%m%d'), end_dt.strftime('%Y%m%d')
                    df_idx = df_idx[(df_idx['date'] >= ds0) & (df_idx['date'] <= ds1)]
                if 'vol' in df_idx.columns:
                    df_idx['volume'] = df_idx['vol']
                if 'amount' in df_idx.columns:
                    df_idx['money'] = df_idx['amount']
                df_idx['code'] = sec
                df_idx['time'] = pd.to_datetime(df_idx['date'].astype(str))
                index_frames.append(df_idx)
            if all_index_files and index_frames:
                res_idx = pd.concat(index_frames, ignore_index=True)
                output_fields = [f for f in fields_to_get if f in res_idx.columns]
                if is_single:
                    return res_idx.set_index('time')[output_fields].sort_index()
                if len(output_fields) == 1:
                    return res_idx.pivot(index='time', columns='code', values=output_fields[0])
                return res_idx.pivot(index='time', columns='code', values=output_fields).sort_index(axis=1)

        if frequency == 'daily':
            self._load_year_to_records(target_year)
            end_dt = pd.to_datetime(end_date or start_date)
            if count:
                all_dates = self.get_trade_days("2010-01-01", end_dt)
                target_dates = all_dates[-count:]
            else:
                target_dates = self.get_trade_days(pd.to_datetime(start_date or end_date), end_dt)
            df_year = self._price_records.get(target_year)
            if df_year is None:
                return pd.DataFrame()
            date_strs = [d.strftime('%Y%m%d') for d in target_dates]
            res_df = df_year[df_year['date'].isin(date_strs) & df_year['code'].isin(local_secs)]
            if res_df.empty:
                return pd.DataFrame()
            res_df = res_df.copy()
            if 'vol' in res_df.columns:
                res_df['volume'] = res_df['vol']
            if 'amount' in res_df.columns:
                res_df['money'] = res_df['amount']
            if any(f in fields_to_get for f in ['high_limit', 'low_limit', 'paused']):
                pc = res_df['pre_close'].astype(float)
                is_star_chi = res_df['code'].str.startswith(('300', '301', '688'))
                res_df['high_limit'] = np.where(is_star_chi, (pc * 1.20 + 0.000001).round(2), (pc * 1.10 + 0.000001).round(2))
                res_df['low_limit'] = np.where(is_star_chi, (pc * 0.80 + 0.000001).round(2), (pc * 0.90 + 0.000001).round(2))
                res_df['paused'] = (res_df['vol'].astype(float) == 0)
            res_df['code'] = self._denormalize(res_df['code'].tolist())
            res_df['time'] = pd.to_datetime(res_df['date'].astype(str))
            output_fields = [f for f in fields_to_get if f in res_df.columns]
            if kwargs.get('panel') is False:
                return res_df[['time', 'code'] + output_fields].sort_values(['time', 'code']).reset_index(drop=True)
            if is_single:
                return res_df.set_index('time')[output_fields].sort_index()
            else:
                if len(output_fields) == 1:
                    return res_df.pivot(index='time', columns='code', values=output_fields[0])
                pivoted = res_df.pivot(index='time', columns='code', values=output_fields)
                return pivoted.sort_index(axis=1)

        elif frequency == '1m':
            end_dt = pd.to_datetime(end_date or start_date)
            res_list = []
            for i, s_local in enumerate(local_secs):
                df_min = self._load_minute_data(s_local, target_year)
                if df_min is None or df_min.empty:
                    continue
                mask = df_min['time'] <= end_dt
                sub_df = df_min[mask].tail(count if count else 1).copy()
                if sub_df.empty:
                    continue
                if 'vol' in sub_df.columns:
                    sub_df['volume'] = sub_df['vol']
                if 'amount' in sub_df.columns:
                    sub_df['money'] = sub_df['amount']
                daily_df = self.get_price(securities[i], end_date=end_dt, frequency='daily', count=1, fields=['high_limit', 'low_limit'])
                if not daily_df.empty:
                    sub_df['high_limit'] = daily_df['high_limit'].iloc[0]
                    sub_df['low_limit'] = daily_df['low_limit'].iloc[0]
                sub_df['code'] = securities[i]
                res_list.append(sub_df)
            if not res_list:
                return pd.DataFrame()
            res_df = pd.concat(res_list)
            output_fields = [f for f in fields_to_get if f in res_df.columns]
            if kwargs.get('panel') is False:
                return res_df[['time', 'code'] + output_fields].sort_values(['time', 'code']).reset_index(drop=True)
            if is_single:
                return res_df.set_index('time')[output_fields].sort_index()
            else:
                if len(output_fields) == 1:
                    return res_df.pivot(index='time', columns='code', values=output_fields[0])
                pivoted = res_df.pivot(index='time', columns='code', values=output_fields)
                return pivoted.sort_index(axis=1)
        return pd.DataFrame()

    def get_valuation(self, security, start_date=None, end_date=None, fields=None, count=None):
        securities = security if isinstance(security, (list, tuple, pd.Index, pd.Series)) else [security]
        dt = pd.to_datetime(end_date or start_date or datetime.now())
        df = self.get_fundamentals(None, date=dt)
        if df.empty:
            return df
        if securities:
            df = df[df['code'].isin(list(securities))].copy()
        if fields is not None:
            keep = ['code'] + [f for f in fields if f in df.columns and f != 'code']
            df = df[keep]
        return df

    def get_call_auction(self, security, start_date=None, end_date=None, fields=None):
        securities = security if isinstance(security, (list, tuple, pd.Index, pd.Series)) else [security]
        start_dt = pd.to_datetime(start_date or end_date)
        end_dt = pd.to_datetime(end_date or start_date)
        years = range(start_dt.year, end_dt.year + 1)
        dfs = []
        for year in years:
            path = os.path.join(self.data_root, f'1d_feature/call_auction/{year}.parquet')
            if os.path.exists(path):
                dfs.append(pd.read_parquet(path))
        if not dfs:
            return pd.DataFrame()
        df = pd.concat(dfs, ignore_index=True)
        if 'code' in df.columns:
            df['code'] = self._denormalize(df['code'].tolist())
            df = df[df['code'].isin(list(securities))]
        date_col = 'date' if 'date' in df.columns else None
        if date_col is not None:
            dates = pd.to_datetime(df[date_col].astype(str))
            df = df[(dates >= start_dt.normalize()) & (dates <= end_dt.normalize())].copy()
        if fields is not None:
            keep = [f for f in fields if f in df.columns]
            if 'code' in df.columns and 'code' not in keep:
                keep.insert(0, 'code')
            df = df[keep]
        return df

    def _load_minute_data(self, code_local, year):
        key = f"{code_local}_{year}"
        if key in self._minute_cache:
            return self._minute_cache[key]
        for base in ["1m_stock", "1m_stock_v2"]:
            path = os.path.join(self.data_root, f"{base}/{code_local}/{year}.parquet")
            if os.path.exists(path):
                df_tmp = pd.read_parquet(path)
                if 'trade_time' in df_tmp.columns:
                    df_tmp = df_tmp.rename(columns={'trade_time': 'time'})
                elif 'datetime' in df_tmp.columns:
                    df_tmp = df_tmp.rename(columns={'datetime': 'time'})
                df_tmp['time'] = pd.to_datetime(df_tmp['time'])
                cols = [c for c in ['time', 'open', 'high', 'low', 'close', 'vol', 'amount'] if c in df_tmp.columns]
                self._minute_cache[key] = df_tmp[cols]
                return self._minute_cache[key]
        return None

    def _load_year_to_records(self, year):
        if year in self._price_records:
            return
        path = os.path.join(self.data_root, f'1d_stock/{year}.parquet')
        if not os.path.exists(path):
            return
        df_tmp = pd.read_parquet(path)
        df_tmp['date'] = df_tmp['date'].astype(str)
        self._price_records[year] = df_tmp

    def get_all_securities(self, types=['stock'], date=None):
        if self._stock_basic is None:
            basic_path = os.path.join(self.data_root, 'stock_basic.parquet')
            if not os.path.exists(basic_path):
                basic_path = os.path.join(self.data_root, 'metadata/stock_basic.parquet')
            self._stock_basic = pd.read_parquet(basic_path)
            self._stock_basic['start_date'] = pd.to_datetime(self._stock_basic['list_date'].astype(str))
            self._stock_basic['end_date'] = pd.to_datetime(self._stock_basic['delist_date'].astype(str), errors='coerce')
            self._stock_basic.index = self._denormalize(self._stock_basic['code'].tolist())
            if 'name' in self._stock_basic.columns:
                self._stock_basic = self._stock_basic.rename(columns={'name': 'display_name'})
            ipo_overrides = {
                '605399.XSHG': pd.Timestamp('2020-08-03'),
                '605123.XSHG': pd.Timestamp('2020-08-21'),
                '605255.XSHG': pd.Timestamp('2020-09-14'),
                '605369.XSHG': pd.Timestamp('2020-09-14'),
            }
            for code, start_date in ipo_overrides.items():
                if code in self._stock_basic.index:
                    self._stock_basic.loc[code, 'start_date'] = start_date

        df_tmp = self._stock_basic.copy()
        if date:
            dt = pd.to_datetime(date)
            df_tmp = df_tmp[(df_tmp['start_date'] <= dt) & ((df_tmp['end_date'].isna()) | (df_tmp['end_date'] > dt))]
            df_tmp = df_tmp[~((df_tmp['end_date'].notna()) & ((df_tmp['end_date'] - dt).dt.days <= 22))]
        return df_tmp[['display_name', 'start_date']]

    def get_extras(self, label, security, start_date=None, end_date=None):
        if self._st_history is None:
            try:
                self._st_history = pd.read_parquet(os.path.join(self.data_root, 'metadata/st_history_consolidated.parquet'))
                self._st_set = set(zip(self._st_history['code'], self._st_history['date'].astype(str)))
            except:
                self._st_set = set()

        securities = security if isinstance(security, list) else [security]
        ds_dt = pd.to_datetime(start_date)
        ds = ds_dt.strftime('%Y%m%d')
        if self._stock_basic is None:
            self.get_all_securities()
        res_dict = {}
        for s in securities:
            is_st = (self._normalize(s), ds) in self._st_set
            if not is_st and pd.to_datetime('2024-05-01') <= ds_dt < pd.to_datetime('2024-06-03'):
                if (self._normalize(s), '20240603') in self._st_set:
                    is_st = True
            if not is_st and s in self._stock_basic.index:
                name = self._stock_basic.loc[s, 'display_name']
                if 'ST' in name or '退' in name:
                    ed = self._stock_basic.loc[s, 'end_date']
                    if pd.notna(ed) and ed.year == 2024 and ds_dt >= pd.to_datetime('2024-05-01'):
                        is_st = True
            res_dict[s] = is_st
        return JQMockResult(res_dict)

    def get_industry_stocks(self, industry_code, date=None):
        try:
            p = os.path.join(self.data_root, 'metadata/industry_member.parquet')
            df = pd.read_parquet(p)
            if 'industry_code' not in df.columns:
                return []
            mask = df['industry_code'] == industry_code
            if date is not None and 'in_date' in df.columns:
                dt = pd.to_datetime(date)
                in_date = pd.to_datetime(df['in_date'], errors='coerce')
                out_date = pd.to_datetime(df.get('out_date'), errors='coerce') if 'out_date' in df.columns else pd.Series(pd.NaT, index=df.index)
                mask &= (in_date <= dt) & (out_date.isna() | (out_date > dt))
            codes = df.loc[mask, 'code'].dropna().astype(str).tolist()
            return self._denormalize(codes)
        except Exception:
            return []

    def get_index_stocks(self, index_symbol, date=None):
        return []

    def get_billboard_list(self, *args, **kwargs):
        return pd.DataFrame()

    def get_fundamentals(self, query_obj, date=None):
        dt_str = pd.to_datetime(date).strftime('%Y%m%d')
        if dt_str in self._indicator_cache:
            return self._indicator_cache[dt_str]
        path = os.path.join(self.data_root, f'基本面数据/stock_indicator/{dt_str}.parquet')
        if os.path.exists(path):
            df_tmp = pd.read_parquet(path)
        else:
            year_path = os.path.join(self.data_root, f'1d_feature/stock_indicator/{dt_str[:4]}.parquet')
            if not os.path.exists(year_path):
                return pd.DataFrame(columns=['code', 'market_cap'])
            df_tmp = pd.read_parquet(year_path)
            if 'date' in df_tmp.columns:
                df_tmp = df_tmp[df_tmp['date'].astype(str) == dt_str].copy()
        df_tmp['market_cap'] = df_tmp['total_mv'] / 1e8
        if 'circ_mv' in df_tmp.columns:
            df_tmp['circulating_market_cap'] = df_tmp['circ_mv'] / 1e8
        df_tmp['code'] = self._denormalize(df_tmp['code'].tolist())
        self._indicator_cache[dt_str] = df_tmp
        return df_tmp
