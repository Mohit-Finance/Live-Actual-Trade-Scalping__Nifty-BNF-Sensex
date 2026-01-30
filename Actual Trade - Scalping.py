import os
import sys
import time
import json
import math
import queue
import threading
import webbrowser
import requests
import pyotp
import keyboard
import pandas as pd
from datetime import datetime
from pathlib import Path
from threading import Thread
import upstox_client
from upstox_client.rest import ApiException
import xlwings as xw
import pythoncom

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

live_data = {}
dict_lock = threading.Lock()
excel_lock = threading.Lock()
access = None

##############################################################################

tdate = datetime.now().date()
code = None

base_dir = Path(__file__).resolve().parent
while base_dir.name != "Live Actual Trade - Scalping":
    if base_dir.parent == base_dir:
        raise FileNotFoundError("'Live Trade - Upstox' folder not found in path hierarchy.")
    base_dir = base_dir.parent


def show_totp(secret):
    totp = pyotp.TOTP(secret)
    otp = totp.now()
    return otp


if not os.path.exists('Credentials/login_details.json'):
    print("User Details not found. First Create a User Base & Retry. Exiting program.")
    sys.exit()

with open('Credentials/login_details.json', 'r') as file_read:
    users_data = json.load(file_read)

allowed_namess = users_data.keys()
allowed_names = [name.lower() for name in allowed_namess]

name_dict = {}

for i in range(len(allowed_names)):
    name_dict[f'{allowed_names[i]}'] = f'{tdate}_access_code_{allowed_names[i]}.json'

name_list = name_dict.values()

os.makedirs(os.path.join('Credentials', 'Data'), exist_ok=True)

file_list = os.listdir(f'Credentials/Data')

for name in name_list:
    if name in file_list:
        with open(f'Credentials/Data/{name}', 'r') as file_read:
            access = json.load(file_read)
            acc_name = name[23:][:-5]

if not access:

    while True:
        acc_name = input(f'\nEnter Name of Account Holder to Login From {list(allowed_namess)} : ').lower()
        if acc_name in allowed_names:
            break
        else:
            print(f"\nInvalid User. Please Enter Registered User Name {list(allowed_namess)}'.")

    try:
        with open(f'Credentials/Data/{tdate}_access_code_{acc_name}.json', 'r') as file_read:
            access = json.load(file_read)

    except:

        with open('Credentials/login_details.json', 'r') as file_read:
            login_details = json.load(file_read)

        api_key = login_details[f'{acc_name.capitalize()}']['api_key']
        api_secret = login_details[f'{acc_name.capitalize()}']['api_secret']
        api_auth = login_details[f'{acc_name.capitalize()}']['api_auth']
        api_pin = login_details[f'{acc_name.capitalize()}']['pin']
        mobile_no = login_details[f'{acc_name.capitalize()}']['Mob No.']
        hold_name = login_details[f'{acc_name.capitalize()}']['full_name']

        print(f'\nTrying to Login from Account Holder: {hold_name}')

        uri = 'https://www.google.com/'
        url1 = f'https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={uri}\n'
        # print(f'\n{url1}\n\n')

        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        driver = uc.Chrome(version_main=144, options=options)
        # driver = uc.Chrome(options=options)

        # driver = uc.Chrome() # Use this line instead to run Chrome in normal (visible) mode, (In that case, comment out the 5 lines above that set headless options)

        driver.get(url1)
        wait = WebDriverWait(driver, 20)
        phone_input = wait.until(EC.presence_of_element_located((By.ID, "mobileNum")))
        phone_input.send_keys(mobile_no)
        otp_button = wait.until(EC.element_to_be_clickable((By.ID, "getOtp")))
        otp_button.click()
        # print("✅ Phone number entered, now captcha should appear normally")

        totp_value = show_totp(api_auth)
        totp_input = wait.until(EC.presence_of_element_located((By.ID, "otpNum")))
        totp_input.send_keys(totp_value)
        proceed_button = wait.until(EC.element_to_be_clickable((By.ID, "continueBtn")))
        proceed_button.click()
        # print("✅ TOTP entered and Continue clicked!")

        pin_input = wait.until(EC.presence_of_element_located((By.ID, "pinCode")))
        pin_input.send_keys(api_pin)
        proceed_button = wait.until(EC.element_to_be_clickable((By.ID, "pinContinueBtn")))
        proceed_button.click()

        # print("✅ PIN entered and proceed button clicked!")
        time.sleep(3)
        code_url = driver.current_url

        driver.quit()

        start = code_url.find('code=')
        if start != -1:
            start =start + 5  # move past 'code='
            code = code_url[start:start+6]
        else:
            print("No code found in the URL")

        url = 'https://api.upstox.com/v2/login/authorization/token'
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'code': code,
            'client_id': api_key,
            'client_secret': api_secret,
            'redirect_uri': uri,
            'grant_type': 'authorization_code',
        }

        response = requests.post(url, headers=headers, data=data)
        access = response.json()['access_token']
        print(f'\nLogin Successful, Status Code : {response.status_code}')
        print(f"User Name : {response.json()['user_name']}\nEmail ID : {response.json()['email']}")

        with open(f'Credentials/Data/{tdate}_access_code_{acc_name}.json', 'w') as file_write:
            json.dump(access, file_write)

print(f'\nLogin Successful from Account : {acc_name.capitalize()}')
hold_name = users_data[f'{acc_name.capitalize()}']['full_name']

configuration = upstox_client.Configuration()
configuration.access_token = access
api_version = '2.0'

streamer_data = None
streamer_portfolio = None
live_data = {}

def on_open_data():
    print("Market Data Streamer Started")

def on_message_data(message):
    # print(message)
    global live_data
    dict_data = message
    if 'feeds' in dict_data:
        data = dict_data['feeds']
        for key, value in data.items():
            ltp = value['ltpc']['ltp']

            with dict_lock:
                live_data[key] = ltp

def data_stream():
    global streamer_data, final_list

    streamer_data = upstox_client.MarketDataStreamerV3(upstox_client.ApiClient(configuration), final_list, "ltpc")

    streamer_data.on("message", on_message_data)
    streamer_data.on("open", on_open_data)
    streamer_data.connect()


buy_order_ce = None
buy_order_pe = None
sell_order_ce = None
sell_order_pe = None
buy_ce_event = threading.Event()
buy_pe_event = threading.Event()
sell_ce_event = threading.Event()
sell_pe_event = threading.Event()

def on_message_portfolio(message):
    global buy_order_ce, buy_order_pe, sell_order_ce, sell_order_pe
    message_dict = json.loads(message)

    if message_dict.get('update_type') == 'order' and message_dict.get('status') == 'complete' and message_dict.get('transaction_type') == 'BUY' and message_dict.get('trading_symbol')[-2:] == 'CE':
        buy_order_ce = message_dict
        buy_ce_event.set()
        # print(buy_order_ce)

    if message_dict.get('update_type') == 'order' and message_dict.get('status') == 'complete' and message_dict.get('transaction_type') == 'BUY' and message_dict.get('trading_symbol')[-2:] == 'PE':
        buy_order_pe = message_dict
        buy_pe_event.set()
        # print(buy_order_pe)

    if message_dict.get('update_type') == 'order' and message_dict.get('status') == 'complete' and message_dict.get('transaction_type') == 'SELL' and message_dict.get('trading_symbol')[-2:] == 'CE':
        sell_order_ce = message_dict
        sell_ce_event.set()

        # print(sell_order_ce)

    if message_dict.get('update_type') == 'order' and message_dict.get('status') == 'complete' and message_dict.get('transaction_type') == 'SELL' and message_dict.get('trading_symbol')[-2:] == 'PE':
        sell_order_pe = message_dict
        sell_pe_event.set()
        # print(sell_order_pe)

def on_open():
    print("Portfolio Data Streamer Started")

def portfolio_stream():
    global streamer_portfolio
    streamer_portfolio = upstox_client.PortfolioDataStreamer(upstox_client.ApiClient(configuration),
                                                  order_update=True,
                                                  position_update=True,
                                                  holding_update=False,
                                                  gtt_update=False)

    streamer_portfolio.on("message", on_message_portfolio)
    streamer_portfolio.on("open", on_open)
    streamer_portfolio.connect()

def main():
    thread1 = threading.Thread(target=data_stream)
    thread2 = threading.Thread(target=portfolio_stream)
    thread1.start()
    thread2.start()


def option_chain(instrument_key,expiry_date,inst,ocs):
    global access
    url = 'https://api.upstox.com/v2/option/chain'
    params = {
            'instrument_key': instrument_key,
            'expiry_date': expiry_date
    }
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access}'
    }

    response = requests.get(url, params=params, headers=headers)
    time.sleep(1)
    time_stamp = datetime.now().strftime("%H:%M:%S")
    option = response.json()
    option_df = pd.json_normalize(option['data'])
    option_df = option_df[['expiry', 'strike_price', 'underlying_spot_price', 'call_options.instrument_key', 'call_options.market_data.ltp',  'put_options.instrument_key', 'put_options.market_data.ltp', ]]
    option_df = option_df.rename(columns={'call_options.instrument_key' : 'CE_instrument_key', 'call_options.market_data.ltp' : 'CE_ltp', 'put_options.instrument_key' : 'PE_instrument_key', 'put_options.market_data.ltp' : 'PE_ltp', 'underlying_spot_price' : 'spot_price'})
    option_df[['signal_ce', 'signal_pe']] = None

    if instrument_key == 'NSE_INDEX|Nifty 50':
        option_df[['lotsize', 'Index']] = [75, 'Nifty 50']
    elif instrument_key == 'NSE_INDEX|Nifty Bank':
        option_df[['lotsize', 'Index']] = [35, 'Bank Nifty']
    else:
        option_df[['lotsize', 'Index']] = [20, 'Sensex']

    option_df['symbol_ce'] = option_df['strike_price'].astype(str) + '_CE'
    option_df['symbol_pe'] = option_df['strike_price'].astype(str) + '_PE'
    
    option_df = option_df[['Index','expiry','lotsize','CE_instrument_key' ,'symbol_ce','CE_ltp','signal_ce','strike_price','signal_pe','PE_ltp','symbol_pe','PE_instrument_key','spot_price']]

    option_df['diff'] = abs(option_df['spot_price'] - option_df['strike_price'])
    ce = option_df.loc[option_df['diff'].idxmin(),'CE_ltp']
    strike = option_df.loc[option_df['diff'].idxmin(),'strike_price']
    pe = option_df.loc[option_df['diff'].idxmin(),'PE_ltp']

    fut_spot_price = ce-pe+strike

    option_df['spot_price'] = fut_spot_price
    option_df['diff'] = abs(option_df['spot_price'] - option_df['strike_price'])
    # option_df['prem_diff'] = option_df['CE_ltp'] - option_df['PE_ltp']
    # option_df['CE/PE'] = round((option_df['CE_ltp'] / option_df['PE_ltp']),2)
    atm_strike = option_df.loc[option_df['diff'].idxmin(), 'strike_price']

    ce_atm_ltp = option_df[option_df['strike_price'] == atm_strike].iloc[0]['CE_ltp']
    pe_atm_ltp = option_df[option_df['strike_price'] == atm_strike].iloc[0]['PE_ltp']

    x = option_df['strike_price'].diff().mode()[0]
    upper_limit = atm_strike + inst*x
    lower_limit = atm_strike - inst*x
    option_df = option_df[(option_df['strike_price'] >= lower_limit) & (option_df['strike_price'] <= upper_limit)]

    list1 = option_df['CE_instrument_key'].tolist()
    list2 = option_df['PE_instrument_key'].tolist()
    t_list = list1 + list2
    return t_list

def instrument():
    inst_url = 'https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz'
    instrument = pd.read_csv(inst_url)
    instrument.to_csv('Credentials/instrument.csv')


def update_subscription_list(inst):
    global expiry_list_nifty, expiry_list_bnf, expiry_list_sensex
    instrument_key_nifty = 'NSE_INDEX|Nifty 50'
    instrument_key_bnf = 'NSE_INDEX|Nifty Bank'
    instrument_key_sensex = 'BSE_INDEX|SENSEX'
    index_ltp = [instrument_key_nifty, instrument_key_bnf, instrument_key_sensex]

    nifty_0_list = option_chain(instrument_key_nifty,expiry_list_nifty[0],inst,ocs=0)
    bnf_0_list = option_chain(instrument_key_bnf,expiry_list_bnf[0],inst,ocs=0)
    sensex_0_list = option_chain(instrument_key_sensex,expiry_list_sensex[0],inst,ocs=0)

    # final_list = nifty_0_list + nifty_1_list + nifty_2_list + nifty_3_list + bnf_0_list + sensex_0_list
    final_list = nifty_0_list + bnf_0_list + sensex_0_list + index_ltp
    return final_list

##############################################################################
try:
    with open(f'Credentials/Data/{tdate}_inputs.json', 'r') as file_read:
        inputs = json.load(file_read)
        ref_inst = inputs['instrument']
        sub_list = inputs['subscription']

except:
    while True:
        # ref_inst = input('Do you want to refresh Instrument Data : 1 / 0 : ')
        ref_inst = '1'
        if ref_inst == '1' or ref_inst == '0':
            break
        else:
            print('Invalid Input, Enter either 1 or 0')

    while True:
        # sub_list = input('\nDo you want to Update Subscription List : 1 / 0 : ')
        sub_list = '1'
        if sub_list == '1' or sub_list == '0':
            break
        else:
            print("\nInvalid Selection. Please enter either '0' or '1'.")

    inputs = {'instrument': 0, 'subscription':0 }

    with open(f'Credentials/Data/{tdate}_inputs.json', 'w') as file_write:
        json.dump(inputs, file_write)

##############################################################################
if ref_inst == '1' :
        instrument()
        print('################---->| Instrument Data Updated |<----################')
else:
    pass

df = pd.read_csv('Credentials/instrument.csv')

df_niftyoptions = df[(df['exchange'] == 'NSE_FO') & (df['instrument_type'] == 'OPTIDX') & (df['name'] == 'NIFTY')]
expiry_list_nifty = df_niftyoptions['expiry'].unique().tolist()
expiry_list_nifty.sort()

df_bnf = df[(df['exchange'] == 'NSE_FO') & (df['instrument_type'] == 'OPTIDX') & (df['name'] == 'BANKNIFTY')]
expiry_list_bnf = df_bnf['expiry'].unique().tolist()
expiry_list_bnf.sort()

df_sensex = df[(df['exchange'] == 'BSE_FO') & (df['instrument_type'] == 'OPTIDX') & (df['name'] == 'SENSEX')]
expiry_list_sensex = df_sensex['expiry'].unique().tolist()
expiry_list_sensex.sort()

##############################################################################

inst = 10 # ATMs +- OTMs you require for each expiry to Subscribe in Websocket

##############################################################################
if sub_list == '1':
    final_list = update_subscription_list(inst)
    print('##########---->| Websocket Subscription List Updated |<----##########')
    with open('Credentials/final_list.json', 'w') as file_write:
        json.dump(final_list, file_write)
else:
    try:
        with open('Credentials/final_list.json', 'r') as file_read:
            final_list = json.load(file_read)
    except:
        final_list = update_subscription_list(inst)
        with open('Credentials/final_list.json', 'w') as file_write:
            json.dump(final_list, file_write)
            print('Subscription List File Not Found, but now Created & Updated')
###############################################################################


if __name__ == "__main__":
    main()

while not live_data:
    print("Waiting for live data to populate...")
    time.sleep(1)


# app = xw.App(visible=True, add_book=False)
# app.display_alerts = False
# wb = app.books.open(f'Scapling.xlsx')

wb = xw.Book('Credentials/Scalping - Actual.xlsx')
nifty = wb.sheets('Nifty')
bnf = wb.sheets('Bank-Nifty')
sensex = wb.sheets('Sensex')


df = pd.read_csv('Credentials/instrument.csv')

df_niftyoptions = df[(df['exchange'] == 'NSE_FO') & (df['instrument_type'] == 'OPTIDX') & (df['name'] == 'NIFTY')]
expiry_list_nifty = df_niftyoptions['expiry'].unique().tolist()
expiry_list_nifty.sort()

df_bnf = df[(df['exchange'] == 'NSE_FO') & (df['instrument_type'] == 'OPTIDX') & (df['name'] == 'BANKNIFTY')]
expiry_list_bnf = df_bnf['expiry'].unique().tolist()
expiry_list_bnf.sort()

df_sensex = df[(df['exchange'] == 'BSE_FO') & (df['instrument_type'] == 'OPTIDX') & (df['name'] == 'SENSEX')]
expiry_list_sensex = df_sensex['expiry'].unique().tolist()
expiry_list_sensex.sort()

condition = True
def hello():
    global condition
    condition = False

run_ce = False
run_pe = False
run_both = False
set_target_2 = False
set_target_0 = False

def set_flag(option):
    global run_ce, run_pe, run_both, set_target_2, set_target_0
    if option == 'ce':
        run_ce = True
    elif option == 'pe':
        run_pe = True
    elif option == 'both' :
        run_both = True

    elif option == 'ce_t2':
        run_ce = True
        set_target_2 = True
    elif option == 'pe_t2':
        run_pe = True
        set_target_2 = True
    elif option == 'both_t2' :
        run_both = True
        set_target_2 = True

    elif option == 'ce_t0':
        run_ce = True
        set_target_0 = True
    elif option == 'pe_t0':
        run_pe = True
        set_target_0 = True
    elif option == 'both_t0' :
        run_both = True
        set_target_0 = True

def buy(tradevalue):
    brokerage = 10
    transaction_charge = 0.0003503 * tradevalue
    sebi_charge = 0.000001 * tradevalue
    gst = 0.18*(brokerage + transaction_charge + sebi_charge)
    stamp_charge = 0.00003*tradevalue
    total = brokerage + transaction_charge + sebi_charge + gst + stamp_charge
    return total

def sell(tradevalue):
    brokerage = 10
    stt = 0.001 * tradevalue
    transaction_charge = 0.0003503 * tradevalue
    sebi_charge = 0.000001 * tradevalue
    gst = 0.18*(brokerage + transaction_charge + sebi_charge)
    total = brokerage + stt + transaction_charge + sebi_charge + gst
    return total


def Brokerage_cal(entrydf):
    summ = []
    for index, row in entrydf.iterrows():
        if index == 'B':
            xy = buy(row['value'])
        if index == 'S':
            xy = sell(row['value'])
        summ.append(xy)

    return int(sum(summ))

keyboard.add_hotkey('z+up', lambda: set_flag('ce'))
keyboard.add_hotkey('x+up', lambda: set_flag('pe'))
keyboard.add_hotkey('b+up', lambda: set_flag('both'))

keyboard.add_hotkey('z+right', lambda: set_flag('ce_t2'))
keyboard.add_hotkey('x+right', lambda: set_flag('pe_t2'))
keyboard.add_hotkey('b+right', lambda: set_flag('both_t2'))

keyboard.add_hotkey('z+left', lambda: set_flag('ce_t0'))
keyboard.add_hotkey('x+left', lambda: set_flag('pe_t0'))
keyboard.add_hotkey('b+left', lambda: set_flag('both_t0'))

keyboard.add_hotkey('r', lambda: reset_margin_check())

last_del_time = 0
double_press_interval = 0.3  # seconds allowed between presses

def on_delete_press(event):
    global last_del_time
    now = time.time()
    
    if run_ce or run_pe or run_both:
        if now - last_del_time <= double_press_interval:
            hello()  # Call your custom function here
            last_del_time = 0
        else:
            last_del_time = now

keyboard.on_press_key("delete", on_delete_press)

def tradelog(df, entry_time, vir_pnl):
    now = datetime.now()
    now_date = now.strftime('%d-%m-%Y')
    now_time = now.time().replace(microsecond=0)
    now_day  = now.strftime('%A')
    time_df = pd.DataFrame([{'Date':now_date, 'Day':now_day, 'Time':entry_time, 'Virtual PNL':vir_pnl}])
    add_df = pd.concat([time_df, df], axis=1).reset_index(drop=True)

    try:
        old_df = pd.read_excel(f'Credentials/Trade_Log/{now_date}_log.xlsx', index_col=0)
    except:
        old_df = pd.DataFrame()

    new_df = pd.concat([old_df, add_df], axis=0).reset_index(drop=True)

    cols = [c for c in new_df.columns if c != 'Virtual PNL'] + ['Virtual PNL']
    new_df = new_df[cols]

    new_df.to_excel(f'Credentials/Trade_Log/{now_date}_log.xlsx')

def tradelog_virtual(df):
    now = datetime.now()
    now_date = now.strftime('%d-%m-%Y')
    now_time = now.time().replace(microsecond=0)
    now_day  = now.strftime('%A')
    time_df = pd.DataFrame([{'Date':now_date, 'Day':now_day, 'Time':now_time}])
    add_df = pd.concat([time_df, df], axis=1).reset_index(drop=True)

    try:
        old_df = pd.read_excel(f'Credentials/Trade_Log/{now_date}_log_virtual.xlsx', index_col=0)
    except:
        old_df = pd.DataFrame()

    new_df = pd.concat([old_df, add_df], axis=0).reset_index(drop=True)

    new_df.to_excel(f'Credentials/Trade_Log/{now_date}_log_virtual.xlsx')

def margin_pnl():
    global configuration, check_margin
    pnl_list = []
    profit, brokerage, net_profit, total_profits, total_losses, total_trades, net_points, pos_sum, neg_sum, trade_acc = (None,) * 10
    profit_virtual, brokerage_virtual, net_profit_virtual, total_profits_virtual, total_losses_virtual, total_trades_virtual, net_points_virtual, pos_sum_virtual, neg_sum_virtual, trade_acc_virtual = (None,) * 10

    now = datetime.now()
    now_date = now.strftime('%d-%m-%Y')
    fund_instance = upstox_client.UserApi(upstox_client.ApiClient(configuration))

    fund_response = fund_instance.get_user_fund_margin(api_version, segment='SEC')
    fund_response = fund_response.to_dict()
    available_margin = fund_response['data']['equity']['available_margin']
    used_margin = fund_response['data']['equity']['used_margin']
    nifty.range('G1').value = available_margin
    nifty.range('G2').value = used_margin


    portfolio_instance = upstox_client.PortfolioApi(upstox_client.ApiClient(configuration))

    portfolio_response1 = portfolio_instance.get_positions(api_version)
    portfolio_response = portfolio_response1.to_dict()
    length = len(portfolio_response['data'])
    for i in range(length):
        pnl = portfolio_response['data'][i]['pnl']
        pnl_list.append(pnl)
    pnl = sum(pnl_list)
    nifty.range('G3').value = pnl

    try:
        df_log = pd.read_excel(f'Credentials/Trade_Log/{now_date}_log.xlsx', index_col=0)
        profit = df_log['Profit'].sum()
        brokerage = df_log['Brokerage'].sum()
        net_profit = df_log['Net Profit'].sum()
        net_points = df_log['Points'].sum()
        vir_pnl = df_log['Virtual PNL'].sum()

        total_trades = len(df_log)
        total_profits = (df_log['Net Profit'] > 0).sum()
        total_losses = (df_log['Net Profit'] <= 0).sum()

        pos_sum = df_log.loc[df_log['Net Profit']>0, 'Net Profit'].sum()
        neg_sum = df_log.loc[df_log['Net Profit']<0, 'Net Profit'].sum()

        trade_acc = round((total_profits/total_trades)*100,2)

    except:
        pass

    nifty.range('G4').value = profit
    nifty.range('G5').value = brokerage
    nifty.range('G6').value = net_profit
    nifty.range('I4').value = net_points

    nifty.range('I4').value = total_profits
    nifty.range('I5').value = total_losses
    nifty.range('I6').value = total_trades

    nifty.range('I3').value = f'{trade_acc} %'

    nifty.range('H2').value = pos_sum
    nifty.range('I2').value = neg_sum


    try:
        df_log_virtual = pd.read_excel(f'Credentials/Trade_Log/{now_date}_log_virtual.xlsx', index_col=0)
        profit_virtual = df_log_virtual['Profit'].sum()
        brokerage_virtual = df_log_virtual['Brokerage'].sum()
        net_profit_virtual = df_log_virtual['Net Profit'].sum()
        net_points_virtual = df_log_virtual['Points'].sum()

        # total_trades_virtual = len(df_log_virtual)
        # total_profits_virtual = (df_log_virtual['Net Profit'] > 0).sum()
        # total_losses_virtual = (df_log_virtual['Net Profit'] <= 0).sum()

        pos_sum_virtual = df_log_virtual.loc[df_log_virtual['Net Profit']>0, 'Net Profit'].sum()
        neg_sum_virtual = df_log_virtual.loc[df_log_virtual['Net Profit']<0, 'Net Profit'].sum()
        # trade_acc_virtual = round((total_profits_virtual/total_trades_virtual)*100,2)

    except:
        pass

    # Virtual Log
    ############################################
    nifty.range('G7').value = profit_virtual
    nifty.range('G8').value = brokerage_virtual
    nifty.range('G9').value = net_profit_virtual
    nifty.range('G10').value = net_points_virtual

    # nifty.range('I7').value = total_profits_virtual
    # nifty.range('I8').value = total_losses_virtual
    # nifty.range('I9').value = total_trades_virtual

    # nifty.range('I10').value = f'{trade_acc_virtual} %'

    nifty.range('H11').value = pos_sum_virtual
    nifty.range('I11').value = neg_sum_virtual


    check_margin = False
    return available_margin

def margin_trade(ce,pe,qty):
    global configuration, margin_check

    margin_instance = upstox_client.ChargeApi(upstox_client.ApiClient(configuration))

    # Sell Margin
    inst_cepe_s = [upstox_client.Instrument(instrument_key=ce,quantity=qty,product="D",transaction_type="SELL"),
                 upstox_client.Instrument(instrument_key=pe,quantity=qty,product="D",transaction_type="SELL")]

    inst_ce_s = [upstox_client.Instrument(instrument_key=ce,quantity=qty,product="D",transaction_type="SELL")]

    inst_pe_s = [upstox_client.Instrument(instrument_key=pe,quantity=qty,product="D",transaction_type="SELL")]

    margin_body_cepe_s = upstox_client.MarginRequest(inst_cepe_s)
    margin_body_ce_s = upstox_client.MarginRequest(inst_ce_s)
    margin_body_pe_s = upstox_client.MarginRequest(inst_pe_s)

    margin_cepe_s = margin_instance.post_margin(margin_body_cepe_s).to_dict()['data']['required_margin']
    margin_ce_s = margin_instance.post_margin(margin_body_ce_s).to_dict()['data']['required_margin']
    margin_pe_s = margin_instance.post_margin(margin_body_pe_s).to_dict()['data']['required_margin']

    sheets[index].range('M9').value = margin_ce_s
    sheets[index].range('N9').value = margin_pe_s
    sheets[index].range('O9').value = margin_cepe_s

    # Buy Margin
    inst_cepe_b = [upstox_client.Instrument(instrument_key=ce,quantity=qty,product="D",transaction_type="BUY"),
                 upstox_client.Instrument(instrument_key=pe,quantity=qty,product="D",transaction_type="BUY")]

    inst_ce_b = [upstox_client.Instrument(instrument_key=ce,quantity=qty,product="D",transaction_type="BUY")]

    inst_pe_b = [upstox_client.Instrument(instrument_key=pe,quantity=qty,product="D",transaction_type="BUY")]

    margin_body_cepe_b = upstox_client.MarginRequest(inst_cepe_b)
    margin_body_ce_b = upstox_client.MarginRequest(inst_ce_b)
    margin_body_pe_b = upstox_client.MarginRequest(inst_pe_b)

    margin_cepe_b = margin_instance.post_margin(margin_body_cepe_b).to_dict()['data']['required_margin']
    margin_ce_b = margin_instance.post_margin(margin_body_ce_b).to_dict()['data']['required_margin']
    margin_pe_b = margin_instance.post_margin(margin_body_pe_b).to_dict()['data']['required_margin']

    sheets[index].range('M4').value = margin_ce_b
    sheets[index].range('N4').value = margin_pe_b
    sheets[index].range('O4').value = margin_cepe_b

    margin_check = False

def reset_margin_check():
    global margin_check
    margin_check = True

def normal_brok(qty, lot, ce_ltp, pe_ltp):
    ce_buy_value = qty*lot*ce_ltp
    ce_brok_dff = pd.DataFrame({'signal':['B', 'S'], 'value':[ce_buy_value, ce_buy_value]})
    ce_brok_dff = ce_brok_dff.set_index('signal')
    ce_brok = Brokerage_cal(ce_brok_dff)

    pe_buy_value = qty*lot*pe_ltp
    pe_brok_dff = pd.DataFrame({'signal':['B', 'S'], 'value':[pe_buy_value, pe_buy_value]})
    pe_brok_dff = pe_brok_dff.set_index('signal')
    pe_brok = Brokerage_cal(pe_brok_dff)

    cepe_brok_dff = pd.DataFrame({'signal':['B', 'B', 'S', 'S'], 'value':[ce_buy_value, pe_buy_value, ce_buy_value, pe_buy_value]})
    cepe_brok_dff = cepe_brok_dff.set_index('signal')
    cepe_brok = Brokerage_cal(cepe_brok_dff)

    sheets[index].range('M6').value = -ce_brok
    sheets[index].range('N6').value = -pe_brok
    sheets[index].range('O6').value = -cepe_brok

m=1
flip = True
check_margin = True
margin_check = True
sheets = {'nifty':nifty, 'bnf':bnf, 'sensex':sensex}
expiry = {'nifty':expiry_list_nifty, 'bnf':expiry_list_bnf, 'sensex':expiry_list_sensex}
segment = {'nifty':'NSE_FO', 'bnf':'NSE_FO', 'sensex':'BSE_FO'}
symbol = {'nifty':'NIFTY', 'bnf':'BANKNIFTY', 'sensex':'SENSEX'}
index_name = {'nifty':'NSE_INDEX|Nifty 50', 'bnf':'NSE_INDEX|Nifty Bank', 'sensex':'BSE_INDEX|SENSEX'}
step_size = {'nifty':50, 'bnf':100, 'sensex':100}
print('#################----------->| Monitoring Started, Ready to Place Trade |<-----------#################')

# Auto Spot ATM Entry in Cell C6 - First Thing
#################################################################################
with dict_lock:
    nifty_spot = live_data[index_name['nifty']]
    bnf_spot = live_data[index_name['bnf']]
    sensex_spot = live_data[index_name['sensex']]

spot_atm_nifty = round(nifty_spot/step_size['nifty'])*step_size['nifty']
spot_atm_bnf = round(bnf_spot/step_size['bnf'])*step_size['bnf']
spot_atm_sensex = round(sensex_spot/step_size['sensex'])*step_size['sensex']

nifty.range('C6').value = spot_atm_nifty
bnf.range('C6').value = spot_atm_bnf
sensex.range('C6').value = spot_atm_sensex
#################################################################################

while True :
    active_sheet = wb.sheets.active
    var = {}

    if check_margin:
        time.sleep(1)
        avail_mar = margin_pnl()

    if active_sheet.name in ('Nifty','Bank-Nifty','Sensex'):

        if active_sheet.name == 'Nifty':
            index = 'nifty'
        elif active_sheet.name == 'Bank-Nifty':
            index = 'bnf'
        elif active_sheet.name == 'Sensex':
            index = 'sensex'

        if flip:
            sheets[index].range('J3:L11').color = (0, 255, 0)
            flip = False
        else:
            sheets[index].range('J3:L11').color = None
            flip = True

        curr_time = datetime.now().strftime("%I:%M:%S %p")
        curr_date = datetime.today().date()
        curr_date_str = curr_date.strftime("%d-%m-%Y")
        today_day = curr_date.strftime("%A")
        sheets[index].range('J1').value = f'{active_sheet.name} : {hold_name.title()} | Today : {curr_date_str} / {today_day} | {curr_time}'

        try :
            var[f'strike_{index}'] = sheets[index].range('C6').value
            var[f'qty_{index}'] = sheets[index].range('C2').value
            var[f'lot_{index}'] = sheets[index].range('C3').value
            var[f'target_{index}'] = sheets[index].range('D11').value
            var[f'sl_{index}'] = sheets[index].range('E11').value
            var[f'maxlot_{index}'] = sheets[index].range('E1').value
            var[f'total_qty_{index}'] = var[f'qty_{index}']*var[f'lot_{index}']
            var[f'{index}_expiry'] = expiry[index][0]
            var[f'df_{index}'] = df[(df['exchange'] == segment[index]) & (df['instrument_type'] == 'OPTIDX') & (df['name'] == symbol[index]) & (df['expiry'] == var[f'{index}_expiry']) & (df['strike'] == var[f'strike_{index}'])]
            var[f'{index}_ce'] = var[f'df_{index}'][var[f'df_{index}']['option_type'] == 'CE'].iloc[0]['instrument_key']

            var[f'ceent_{index}'] = sheets[index].range('B9').value
            var[f'peent_{index}'] = sheets[index].range('D9').value
            var[f'signal_{index}'] = str(sheets[index].range('C9').value or "").lower()

            var[f'trade_ce_{index}'] = sheets[index].range('I8').value
            var[f'trade_pe_{index}'] = sheets[index].range('I9').value

            reset_tar = sheets[index].range('I10').value

            with dict_lock:
                var[f'{index}_ce_ltp'] = live_data.get(var[f'{index}_ce'])

            sheets[index].range('B6').value = var[f'{index}_ce_ltp']

            var[f'{index}_pe'] = var[f'df_{index}'][var[f'df_{index}']['option_type'] == 'PE'].iloc[0]['instrument_key']

            with dict_lock:
                var[f'{index}_pe_ltp'] = live_data.get(var[f'{index}_pe'])
                var[f'{index}_spot'] = live_data.get(index_name[index])

            synthetic_spot = var[f'{index}_ce_ltp'] - var[f'{index}_pe_ltp'] + var[f'strike_{index}']

            synthetic_atm = round(synthetic_spot/step_size[index])*step_size[index]
            sheets[index].range('B7').value = f'Synthetic ATM Strike : {synthetic_atm}'

            atm = round(var[f'{index}_spot']/step_size[index])*step_size[index]
            sheets[index].range('C7').value = atm

            sheets[index].range('D6').value = var[f'{index}_pe_ltp']
            sheets[index].range('C1').value = var[f'{index}_spot']
            sheets[index].range('C4').value = var[f'{index}_expiry']

            max_ce_lot = avail_mar//(var[f'qty_{index}']*var[f'{index}_ce_ltp'])
            max_pe_lot = avail_mar//(var[f'qty_{index}']*var[f'{index}_pe_ltp'])
            max_cepe_lot = int(avail_mar//((var[f'qty_{index}']*var[f'{index}_pe_ltp']) + (var[f'qty_{index}']*var[f'{index}_ce_ltp'])))
            sheets[index].range('D3').value = f'{int(max_ce_lot)} Lot'
            sheets[index].range('E3').value = f'{int(max_pe_lot)} Lot'
            sheets[index].range('E5').value = f'CE-PE : {max_cepe_lot} Lot'

            ce_margin = max_ce_lot*var[f'{index}_ce_ltp']*var[f'qty_{index}']
            pe_margin = max_pe_lot*var[f'{index}_pe_ltp']*var[f'qty_{index}']
            cepe_margin = max_cepe_lot*((var[f'qty_{index}']*var[f'{index}_pe_ltp']) + (var[f'qty_{index}']*var[f'{index}_ce_ltp']))

            sheets[index].range('D4').value = f'{int(ce_margin)} Rs'
            sheets[index].range('E4').value = f'{int(pe_margin)} Rs'
            sheets[index].range('E6').value = f'{int(cepe_margin)} Rs'

        except Exception as e:
            print(f'Error Occured :{e}')
            pass

        sheets[index].range('E7').value = f"{int(var[f'qty_{index}']*var[f'lot_{index}'])} Qty"

        curr_exp = datetime.strptime(var[f'{index}_expiry'], "%Y-%m-%d").date()
        exp_day = curr_exp.strftime("%A")[:3]
        dte = (curr_exp - curr_date).days
        sheets[index].range('E9').value = f'{dte} DTE ({exp_day})'

        if margin_check:
            margin_trade(var[f'{index}_ce'], var[f'{index}_pe'], var[f'qty_{index}'])
            normal_brok(var[f'qty_{index}'], var[f'lot_{index}'], var[f'{index}_ce_ltp'], var[f'{index}_pe_ltp'])

        if (var[f'signal_{index}'] == 'bbo'): # Buy Break-Out
            if (var[f'ceent_{index}'] != 0) and (var[f'{index}_ce_ltp'] >= var[f'ceent_{index}']):
                set_flag('ce')
            elif (var[f'peent_{index}'] != 0) and (var[f'{index}_pe_ltp'] >= var[f'peent_{index}']):
                set_flag('pe')

        elif (var[f'signal_{index}'] == 'blo'): # Buy Limit Order
            if (var[f'ceent_{index}'] != 0) and (var[f'{index}_ce_ltp'] <= var[f'ceent_{index}']):
                set_flag('ce')
            elif (var[f'peent_{index}'] != 0) and (var[f'{index}_pe_ltp'] <= var[f'peent_{index}']):
                set_flag('pe')

        # # For Activating Blue Area in Trading Terminal
        # entry_time_sec = datetime.now().time().second
        # sheets[index].range('I7').value = entry_time_sec

        # if entry_time_sec == 59:
        #     if var[f'trade_ce_{index}']:
        #         set_flag('ce')
        #     elif var[f'trade_pe_{index}']:
        #         set_flag('pe')

        if run_ce or run_pe:

            if set_target_2:
                sheets[index].range('D11').value = 2
                var[f'target_{index}'] = 2
                set_target_2 = False

            if set_target_0:
                sheets[index].range('D11').value = 0
                var[f'target_{index}'] = 0
                set_target_0 = False

            # sheets[index].range('D11').value = 0
            # sheets[index].range('E11').value = 0
            sheets[index].range('I8').value = 0
            sheets[index].range('I9').value = 0

            if run_ce:
                if var[f'lot_{index}'] > max_ce_lot :
                    sheets[index].range('B8:E8').color = (255, 0, 0) # Red Color
                    sheets[index].range('B8').value = 'Failed : CE Lot Size Exceeded than Max Allowed'
                    run_ce = False
                    continue

            if run_pe:
                if var[f'lot_{index}'] > max_pe_lot :
                    sheets[index].range('B8:E8').color = (255, 0, 0) # Red Color
                    sheets[index].range('B8').value = 'Failed : PE Lot Size Exceeded than Max Allowed'
                    run_pe = False
                    continue

            sheets[index].range("A13:T30").clear_contents()
            
            print("Executing CE logic inline...") if run_ce else print("Executing PE logic inline...")
            structure = {'Index':None, 'Inst Token':None,  'Entry Date':None, 'Expiry':None, 'Strike':None, 'Type':None, 'Qty/Lot':None, 'Lot':None, 'Buy Qty':None, 'Entry Time':None, 'Exit Time':None, 'Entry Price':None, 'Exit Price':None, 'LTP':None, 'Points':None, 'Profit':None, 'Brokerage':None, 'Net Profit':None, 'Gain':None, 'Margin':None}

            body = upstox_client.PlaceOrderV3Request(quantity=var[f'total_qty_{index}'], product="I", validity="DAY", 
                price=0, tag="string", instrument_token=var[f'{index}_ce'] if run_ce else var[f'{index}_pe'], 
                order_type="MARKET", transaction_type="BUY", disclosed_quantity=0, 
                trigger_price=0.0, is_amo=False, slice=True)

            place_order_instance = upstox_client.OrderApiV3(upstox_client.ApiClient(configuration))
            place_order_response = place_order_instance.place_order(body)

            if run_ce:
                buy_ce_event.wait()     # blocks instantly, no CPU, no delay
                buy_ce_event.clear()
            else:
                buy_pe_event.wait()
                buy_pe_event.clear()


            sheets[index].range('B8:E8').color = (0, 255, 0) # Green Color
            sheets[index].range('B8').value = 'Success : CE Trade Placed Successfully' if run_ce else 'Success : PE Trade Placed Successfully'

            structure['Inst Token'] = buy_order_ce['instrument_token'] if run_ce else buy_order_pe['instrument_token']

            entry_order_timestamp = buy_order_ce['order_timestamp'] if run_ce else buy_order_pe['order_timestamp']
            date_str, time_str = entry_order_timestamp.split(' ')
            structure['Entry Date'] = date_str
            structure['Strike'] = var[f'strike_{index}']
            structure['Type'] = buy_order_ce['trading_symbol'][-2:] if run_ce else buy_order_pe['trading_symbol'][-2:]
            structure['Expiry'] = var[f'{index}_expiry']
            structure['Index'] = active_sheet.name
            structure['Qty/Lot'] = var[f'qty_{index}']
            structure['Lot'] = var[f'lot_{index}']
            structure['Entry Time'] = time_str
            structure['Exit Time'] = None

            structure['Buy Qty'] = buy_order_ce['filled_quantity'] if run_ce else buy_order_pe['filled_quantity']
            structure['Entry Price'] = buy_order_ce['average_price'] if run_ce else buy_order_pe['average_price']
            structure['Exit Price'] = None
            buy_value = structure['Buy Qty'] * structure['Entry Price']

            buy_value_virtual = var[f'qty_{index}']*var[f'maxlot_{index}'] * structure['Entry Price']####################

            margin = buy_value

            sheets[index].range("A13:T30").clear_contents()

            while True:
                with dict_lock:
                    structure['LTP'] = live_data.get(var[f'{index}_ce']) if run_ce else live_data.get(var[f'{index}_pe'])

                structure['Points'] = (structure['LTP'] - structure['Entry Price'])
                structure['Profit'] = (structure['LTP'] - structure['Entry Price'])*structure['Buy Qty']
                sell_value = structure['Buy Qty'] * structure['LTP']
                sell_value_virtual = var[f'qty_{index}']*var[f'maxlot_{index}'] * structure['LTP']####################

                # brok_df = pd.DataFrame([buy_value, sell_value], index=['B', 'S'], columns=['value'])
                brok_df = pd.DataFrame({'signal': ['B', 'S'], 'value':[buy_value, sell_value]})
                brok_df.set_index('signal', inplace=True)
                brokerage = Brokerage_cal(brok_df)

                brok_df_virtual = pd.DataFrame({'signal': ['B', 'S'], 'value':[buy_value_virtual, sell_value_virtual]})################
                brok_df_virtual.set_index('signal', inplace=True)################
                brokerage_virtual = Brokerage_cal(brok_df_virtual) ##################

                structure['Brokerage'] = - brokerage
                structure['Net Profit'] = structure['Profit'] + structure['Brokerage']
                structure['Gain'] = f"{round((structure['Net Profit'] / margin)*100,2)} %"
                structure['Margin'] = margin

                df_str = pd.DataFrame([structure])
                df_excel = df_str[['Index', 'Strike', 'Type', 'Lot', 'Buy Qty', 'Entry Price', 'Exit Price', 'LTP', 'Points', 'Profit', 'Brokerage', 'Net Profit', 'Gain', 'Margin']]
                sheets[index].range('A13').value = df_excel

                ###############################################
                df_virtual = df_excel.copy()
                df_virtual['Lot'] = var[f'maxlot_{index}']
                df_virtual['Buy Qty'] = var[f'qty_{index}']*var[f'maxlot_{index}']
                df_virtual['Profit'] = (df_virtual['LTP'] - df_virtual['Entry Price'])*df_virtual['Buy Qty']
                df_virtual['Brokerage'] = -brokerage_virtual
                df_virtual['Net Profit'] = df_virtual['Profit'] + df_virtual['Brokerage']
                df_virtual = df_virtual[['Index', 'Strike', 'Type', 'Lot', 'Buy Qty', 'Entry Price', 'Exit Price', 'LTP', 'Points', 'Profit', 'Brokerage', 'Net Profit']]
                sheets[index].range('A16').value = df_virtual


                if (var[f'target_{index}'] != 0 and structure['Points']>=var[f'target_{index}']) or (var[f'sl_{index}'] != 0 and structure['Points']<=(-var[f'sl_{index}'])):
                    if structure['Points'] >= var[f'target_{index}']:
                        sheets[index].range('D11').color = (0, 255, 0)
                    else:
                        sheets[index].range('E11').color = (255, 0, 0)
                    hello()

                if not condition :
                    exit_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
                    exit_response = exit_instance.exit_positions()

                    if run_ce:
                        sell_ce_event.wait()
                        sell_ce_event.clear()
                    else:
                        sell_pe_event.wait()
                        sell_pe_event.clear()



                    sell_qty = sell_order_ce['filled_quantity'] if run_ce else sell_order_pe['filled_quantity']
                    structure['Exit Price'] = sell_order_ce['average_price'] if run_ce else sell_order_pe['average_price']
                    structure['Points'] = (structure['Exit Price'] - structure['Entry Price'])
                    structure['Profit'] = (structure['Exit Price'] - structure['Entry Price'])*sell_qty

                    sell_value = sell_qty * structure['Exit Price']
                    sell_value_virtual = var[f'qty_{index}']*var[f'maxlot_{index}'] * structure['Exit Price']

                    # brok_df = pd.DataFrame([buy_value, sell_value], index=['B', 'S'], columns=['value'])
                    brok_df = pd.DataFrame({'signal': ['B', 'S'], 'value':[buy_value, sell_value]})
                    brok_df.set_index('signal', inplace=True)
                    brokerage = Brokerage_cal(brok_df)

                    brok_df_virtual = pd.DataFrame({'signal': ['B', 'S'], 'value':[buy_value_virtual, sell_value_virtual]})###########################
                    brok_df_virtual.set_index('signal', inplace=True)###########################
                    brokerage_virtual = Brokerage_cal(brok_df_virtual)###########################

                    exit_order_timestamp = sell_order_ce['order_timestamp'] if run_ce else sell_order_pe['order_timestamp']
                    date_str, time_str = exit_order_timestamp.split(' ')
                    structure['Exit Time'] = time_str

                    structure['Brokerage'] = -brokerage
                    structure['Net Profit'] = structure['Profit'] + structure['Brokerage']
                    structure['Gain'] = f"{round((structure['Net Profit'] / margin)*100,2)} %"

                    df_str = pd.DataFrame([structure])
                    #################################-----------------------@@@@@@@@@@@@@@@------------------%%%%%%%%%%%%%%%%%------------------###############################################
                    df_log = df_str.copy()
                    df_excel = df_str[['Index', 'Strike', 'Type', 'Lot', 'Buy Qty', 'Entry Price', 'Exit Price', 'LTP', 'Points', 'Profit', 'Brokerage', 'Net Profit', 'Gain', 'Margin']]
                    sheets[index].range('A13').value = df_excel

                    ################################################
                    df_virtual = df_excel.copy()
                    df_virtual['Lot'] = var[f'maxlot_{index}']
                    df_virtual['Buy Qty'] = var[f'qty_{index}']*var[f'maxlot_{index}']
                    df_virtual['Profit'] = (structure['Exit Price'] - structure['Entry Price'])*df_virtual['Buy Qty']
                    df_virtual['Brokerage'] = -brokerage_virtual
                    df_virtual['Net Profit'] = df_virtual['Profit'] + df_virtual['Brokerage']
                    df_virtual = df_virtual[['Index', 'Strike', 'Type', 'Lot', 'Buy Qty', 'Entry Price', 'Exit Price', 'LTP', 'Points', 'Profit', 'Brokerage', 'Net Profit']]
                    sheets[index].range('A16').value = df_virtual

                    tradelog(df_excel, structure['Entry Time'], df_virtual['Net Profit'].iloc[0])
                    tradelog_virtual(df_virtual)
                    condition = True
                    m=1
                    buy_order_ce = None
                    sell_order_ce = None
                    buy_order_pe = None
                    sell_order_pe = None
                    check_margin = True
                    run_ce = False
                    run_pe = False
                    sheets[index].range('B8').color = None
                    sheets[index].range('B8').value = 'Position Closed Successfully'

                    if reset_tar:
                        sheets[index].range('D11').value = reset_tar
                        
                    print('Position Closed')
                    break
            
        if run_both:

            if set_target_2:
                sheets[index].range('D11').value = 2
                var[f'target_{index}'] = 2
                set_target_2 = False

            elif set_target_0:
                sheets[index].range('D11').value = 0
                var[f'target_{index}'] = 0
                set_target_0 = False

            sheets[index].range('D11').value = 0
            sheets[index].range('E11').value = 0

            if var[f'lot_{index}'] > max_cepe_lot :
                sheets[index].range('B8:E8').color = (255, 0, 0) # Red Color
                sheets[index].range('B8').value = 'Failed : CE-PE Lot Size Exceeded than Max Allowed'
                run_both = False
                continue

            run_both = False
            print("Executing PE-CE logic inline...")

            structure = {'Index':[None, None], 'Inst Token':[None, None],  'Entry Date':[None, None], 'Expiry':[None, None], 'Strike':[None, None], 'Type':[None, None], 'Qty/Lot':[None, None], 'Lot':[None, None], 'Buy Qty':[None, None], 'Entry Time':[None, None], 'Exit Time':[0.0, 0.0], 'Entry Price':[None, None], 'Exit Price':[None, None], 'LTP':[None, None], 'Points':[None, None], 'Profit':[None, None]}

            place_order_instance = upstox_client.OrderApiV3(upstox_client.ApiClient(configuration))
            ###########################################################
            body = upstox_client.PlaceOrderV3Request(quantity=var[f'total_qty_{index}'], product="I", validity="DAY", 
                price=0, tag="string", instrument_token=var[f'{index}_ce'], 
                order_type="MARKET", transaction_type="BUY", disclosed_quantity=0, 
                trigger_price=0.0, is_amo=False, slice=True)

            place_order_response_ce = place_order_instance.place_order(body)

            ###########################################################
            body = upstox_client.PlaceOrderV3Request(quantity=var[f'total_qty_{index}'], product="I", validity="DAY", 
                price=0, tag="string", instrument_token=var[f'{index}_pe'], 
                order_type="MARKET", transaction_type="BUY", disclosed_quantity=0, 
                trigger_price=0.0, is_amo=False, slice=True)

            place_order_response_pe = place_order_instance.place_order(body)

            buy_ce_event.wait()
            buy_pe_event.wait()

            buy_ce_event.clear()
            buy_pe_event.clear()            

            sheets[index].range('B8:E8').color = (0, 255, 0) # Green Color
            sheets[index].range('B8').value = 'Success : CE-PE Trade Placed Successfully'
            
            structure['Index'] = [active_sheet.name, active_sheet.name]
            structure['Inst Token'] = [buy_order_ce['instrument_token'], buy_order_pe['instrument_token']]
            structure['Entry Date'] = [buy_order_ce['order_timestamp'].split(' ')[0], buy_order_pe['order_timestamp'].split(' ')[0]]
            structure['Expiry'] = [var[f'{index}_expiry'], var[f'{index}_expiry']]
            structure['Strike'] = [var[f'strike_{index}'], var[f'strike_{index}']]
            structure['Type'] = [buy_order_ce['trading_symbol'][-2:], buy_order_pe['trading_symbol'][-2:]]
            structure['Qty/Lot'] = [var[f'qty_{index}'], var[f'qty_{index}']]
            structure['Lot'] = [var[f'lot_{index}'], var[f'lot_{index}']]
            structure['Buy Qty'] = [buy_order_ce['filled_quantity'], buy_order_pe['filled_quantity']]
            structure['Entry Time'] = [buy_order_ce['order_timestamp'].split(' ')[1], buy_order_pe['order_timestamp'].split(' ')[1]]
            structure['Entry Price'] = [buy_order_ce['average_price'], buy_order_pe['average_price']]
            buy_value = (structure['Buy Qty'][0] * structure['Entry Price'][0]) + (structure['Buy Qty'][1] * structure['Entry Price'][1])
            margin = round(buy_value,2)

            sheets[index].range("A13:T30").clear_contents()

            while True:
                with dict_lock:
                    structure['LTP'] = [live_data.get(var[f'{index}_ce']), live_data.get(var[f'{index}_pe'])]

                structure['Points'] = [(structure['LTP'][0] - structure['Entry Price'][0]), (structure['LTP'][1] - structure['Entry Price'][1])]
                structure['Profit'] = [((structure['LTP'][0] - structure['Entry Price'][0])*structure['Buy Qty'][0]), ((structure['LTP'][1] - structure['Entry Price'][1])*structure['Buy Qty'][1])]

                bv1 = structure['Buy Qty'][0] * structure['Entry Price'][0]
                bv2 = structure['Buy Qty'][1] * structure['Entry Price'][1]
                sv1 = structure['Buy Qty'][0] * structure['LTP'][0]
                sv2 = structure['Buy Qty'][1] * structure['LTP'][1]

                brok_df = pd.DataFrame({'signal':['B', 'B', 'S', 'S'], 'value':[bv1, bv2, sv1, sv2]})
                brok_df.set_index('signal', inplace=True)
                # brok_df = pd.DataFrame([bv1, bv2, sv1, sv2], index=['B', 'B', 'S', 'S'], columns=['value'])
                brokerage = - Brokerage_cal(brok_df)

                df_str = pd.DataFrame(structure)
                net_points = df_str['Points'].sum()
                total_profit = df_str['Profit'].sum()
                net_profit = total_profit + brokerage
                gain = round((net_profit/margin)*100,2)

                new_rows_df = pd.DataFrame([{'LTP':net_points, 'Points':'Total Profit',  'Profit': total_profit},
                                         {'Points': 'Brokerage', 'Profit': brokerage},
                                         {'Points': 'Net Profit', 'Profit': net_profit}, 
                                         {'Entry Price': 'Margin', 'Exit Price':margin, 'Points': 'Gain %', 'Profit': f'{gain} %'}], columns=df_str.columns)
                dff_str = df_str.copy()
                df_str = df_str.astype(object)
                new_rows_df = new_rows_df.astype(object)

                both_df = pd.concat([df_str, new_rows_df], ignore_index=True)
                both_df_excel = both_df[['Index', 'Strike', 'Type', 'Lot', 'Buy Qty', 'Entry Price', 'Exit Price', 'LTP', 'Points', 'Profit']]
                sheets[index].range('A13').value = both_df_excel

                if (var[f'target_{index}'] != 0 and net_points>=var[f'target_{index}']) or (var[f'sl_{index}'] != 0 and net_points<=(-var[f'sl_{index}'])):
                    if net_points >= var[f'target_{index}']:
                        sheets[index].range('D11').color = (0, 255, 0)
                    else:
                        sheets[index].range('E11').color = (255, 0, 0)
                    hello()


                if not condition :
                    exit_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
                    exit_response = exit_instance.exit_positions()

                    sell_ce_event.wait()
                    sell_pe_event.wait()

                    sell_ce_event.clear()
                    sell_pe_event.clear() 

                    sum_exit_price = sell_order_ce['average_price'] + sell_order_pe['average_price']
                    structure['Exit Price'] = [sell_order_ce['average_price'], sell_order_pe['average_price']]
                    structure['Exit Time'] = [sell_order_ce['order_timestamp'].split(' ')[1], sell_order_pe['order_timestamp'].split(' ')[1]]
                    structure['Points'] = [(structure['Exit Price'][0] - structure['Entry Price'][0]), (structure['Exit Price'][1] - structure['Entry Price'][1])]
                    structure['Profit'] = [((structure['Exit Price'][0] - structure['Entry Price'][0])*structure['Buy Qty'][0]), ((structure['Exit Price'][1] - structure['Entry Price'][1])*structure['Buy Qty'][1])]

                    bv1 = structure['Buy Qty'][0] * structure['Entry Price'][0]
                    bv2 = structure['Buy Qty'][1] * structure['Entry Price'][1]
                    sv1 = structure['Buy Qty'][0] * structure['Exit Price'][0]
                    sv2 = structure['Buy Qty'][1] * structure['Exit Price'][1]

                    brok_df = pd.DataFrame({'signal':['B', 'B', 'S', 'S'], 'value':[bv1, bv2, sv1, sv2]})
                    brok_df.set_index('signal', inplace=True)
                    # brok_df = pd.DataFrame([bv1, bv2, sv1, sv2], index=['B', 'B', 'S', 'S'], columns=['value'])
                    brokerage = - Brokerage_cal(brok_df)

                    df_str = pd.DataFrame(structure)
                    net_points = df_str['Points'].sum()
                    total_profit = df_str['Profit'].sum()
                    net_profit = total_profit + brokerage
                    gain = round((net_profit/margin)*100,2)

                    new_rows_df = pd.DataFrame([{'LTP':net_points, 'Points':'Total Profit',  'Profit': total_profit},
                                             {'Points': 'Brokerage', 'Profit': brokerage},
                                             {'Points': 'Net Profit', 'Profit': net_profit}, 
                                             {'Entry Price': 'Margin', 'Exit Price':margin, 'Points': 'Gain %', 'Profit': f'{gain} %'}])
                    

                    both_df = pd.concat([df_str, new_rows_df], ignore_index=True)
                    both_df_excel = both_df[['Index', 'Strike', 'Type', 'Lot', 'Buy Qty', 'Entry Price', 'Exit Price', 'LTP', 'Points', 'Profit']]
                    sheets[index].range('A13').value = both_df_excel
                    df_excel = pd.DataFrame([{'Index':both_df_excel.at[0,'Index'], 'Strike':both_df_excel.at[0,'Strike'], 'Type':'CE-PE', 'Lot':both_df_excel.at[0, 'Lot'], 'Buy Qty': both_df_excel.at[0,'Buy Qty'], 'Entry Price':dff_str['Entry Price'].sum(),  'Exit Price':sum_exit_price, 'LTP':dff_str['LTP'].sum(), 'Points':both_df_excel.at[2, 'LTP'], 'Profit':both_df_excel.at[2, 'Profit'], 'Brokerage':both_df_excel.at[3, 'Profit'], 'Net Profit':both_df_excel.at[4, 'Profit'], 'Gain':both_df_excel.at[5,'Profit'], 'Margin':both_df_excel.at[5, 'Exit Price']}])
                    vir_pnl = 0
                    tradelog(df_excel, structure['Entry Time'], vir_pnl)
                    condition = True
                    m=1
                    buy_order_ce = None
                    buy_order_pe = None
                    sell_order_ce = None
                    sell_order_pe = None
                    check_margin = True
                    sheets[index].range('B8').color = None
                    sheets[index].range('B8').value = 'Position Closed Successfully'

                    if reset_tar:
                        sheets[index].range('D11').value = reset_tar
                        
                    print('Position Closed')
                    break

