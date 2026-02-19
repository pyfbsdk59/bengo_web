from django.shortcuts import render, redirect
from django.contrib import messages
from .models import StockData
import json
from datetime import datetime, timedelta
import traceback

def dashboard(request):
    # --- 上傳邏輯 ---
    if request.method == 'POST' and request.FILES.get('json_file'):
        try:
            f = request.FILES['json_file']
            data = json.load(f)
            
            stock_id = data.get('stock_id')
            stock_name = data.get('stock_name')
            history = data.get('history', [])

            print(f"DEBUG: 準備匯入 {stock_id} {stock_name}, 共 {len(history)} 筆原始資料") # Render Log

            # 強壯的清洗函式
            def clean_int(v):
                if v is None or v == "": return 0
                try:
                    s = str(v).replace(',', '').strip()
                    f = float(s) # 先轉 float 吃掉 .0
                    return int(f)
                except: return 0

            def clean_float(v):
                if v is None or v == "": return 0.0
                try:
                    return float(str(v).replace(',', '').replace('%', '').strip())
                except: return 0.0

            batch_data = []
            
            for row in history:
                # 日期處理 (最容易錯的地方)
                d_val = row.get('date')
                if not d_val: continue
                
                # 處理 "20260219.0" 或 20260219
                d_str = str(d_val).split('.')[0].strip()
                
                try:
                    date_obj = datetime.strptime(d_str, "%Y%m%d").date()
                except ValueError:
                    print(f"DEBUG: 日期格式錯誤跳過: {d_str}")
                    continue
                
                # 建立物件
                obj = StockData(
                    stock_id=stock_id,
                    stock_name=stock_name,
                    date=date_obj,
                    price=clean_float(row.get('price')),
                    total_shares=clean_int(row.get('total_shares')),
                    total_people=clean_int(row.get('total_people')),
                    bengo_threshold=row.get('threshold_str', ''),
                    major_people=clean_int(row.get('major_ppl')),
                    major_pct=clean_float(row.get('major_pct')),
                    note=row.get('note', '')
                )
                batch_data.append(obj)
            
            print(f"DEBUG: 解析完成，準備寫入 {len(batch_data)} 筆資料")

            if batch_data:
                # [關鍵修正] 改用 ignore_conflicts=True
                # 這會 "忽略重複的資料"，只寫入新的日期，最不容易報錯
                StockData.objects.bulk_create(
                    batch_data,
                    ignore_conflicts=True 
                )
                messages.success(request, f"成功匯入 {len(batch_data)} 筆資料！")
            else:
                messages.warning(request, "警告：JSON 檔案中沒有有效的資料，或日期格式解析失敗。")

            return redirect(f'/?stock={stock_id}')
            
        except Exception as e:
            print(traceback.format_exc()) # 印出完整錯誤到 Render Log
            messages.error(request, f"系統錯誤: {e}")

# --- 查詢邏輯 ---
    query_stock = request.GET.get('stock', '')
    chart_data = {}
    table_data = []
    stock_name_display = ""
    
    # [新增] 抓取資料庫內所有不重複的股票代號與名稱，供清單顯示
    all_stocks = StockData.objects.values('stock_id', 'stock_name').distinct().order_by('stock_id')
    
    if query_stock:
        # 抓取該股票資料 (表格用，倒序)
        qs_all = StockData.objects.filter(stock_id=query_stock).order_by('-date')
        
        if qs_all.exists():
            stock_name_display = qs_all.first().stock_name
            table_data = qs_all
            
            # 圖表資料 (只抓最近 180 天，正序)
            six_months_ago = datetime.now().date() - timedelta(days=180)
            qs_chart = qs_all.filter(date__gte=six_months_ago).order_by('date')
            
            # 如果半年內沒資料，抓最後 30 筆
            if not qs_chart.exists():
                 qs_chart = qs_all.order_by('-date')[:30][::-1]

            chart_data = {
                'dates': [d.date.strftime('%Y/%m/%d') for d in qs_chart],
                'prices': [d.price for d in qs_chart],
                'major_pcts': [d.major_pct for d in qs_chart]
            }
        else:
            stock_name_display = query_stock
            messages.info(request, f"資料庫中找不到代號 {query_stock} 的資料。")

    return render(request, 'dashboard.html', {
        'chart_data': json.dumps(chart_data),
        'table_data': table_data,
        'query_stock': query_stock,
        'stock_name_display': stock_name_display,
        'all_stocks': all_stocks  # [新增] 將所有股票清單傳給前端
    })s