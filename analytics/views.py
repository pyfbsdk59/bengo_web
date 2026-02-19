from django.shortcuts import render, redirect
from django.contrib import messages
from .models import StockData
import json
from datetime import datetime

# 首頁：上傳 + 查詢
def dashboard(request):
    # 處理 JSON 上傳
    if request.method == 'POST' and request.FILES.get('json_file'):
        try:
            f = request.FILES['json_file']
            data = json.load(f)
            
            stock_id = data.get('stock_id')
            stock_name = data.get('stock_name')
            history = data.get('history', [])

            # [關鍵修正] 更強壯的整數轉換函式
            def clean_int(v):
                if v is None or v == "": return 0
                try:
                    # 1. 先轉成字串
                    s = str(v)
                    # 2. 去掉逗號
                    s = s.replace(',', '').strip()
                    # 3. 先轉 float (處理 '25932525.0' 這種情況)
                    f = float(s)
                    # 4. 最後轉 int
                    return int(f)
                except:
                    return 0

            # 浮點數轉換函式
            def clean_float(v):
                if v is None or v == "": return 0.0
                try:
                    return float(str(v).replace(',', '').replace('%', '').strip())
                except:
                    return 0.0

            count = 0
            for row in history:
                # 日期格式轉換
                # 您的 JSON 日期可能是 20260218 (數字) 或 "20260218" (字串)
                d_val = row.get('date')
                d_str = str(d_val).split('.')[0] # 防呆：如果是 20260218.0，去掉小數
                
                try:
                    date_obj = datetime.strptime(d_str, "%Y%m%d").date()
                except ValueError:
                    # 如果日期格式不對，跳過這一行
                    continue
                
                # 存入資料庫
                StockData.objects.update_or_create(
                    stock_id=stock_id,
                    date=date_obj,
                    defaults={
                        'stock_name': stock_name,
                        'price': clean_float(row.get('price')),
                        'total_shares': clean_int(row.get('total_shares')), # 使用新函式
                        'total_people': clean_int(row.get('total_people')), # 使用新函式
                        'bengo_threshold': row.get('threshold_str', ''),
                        'major_people': clean_int(row.get('major_ppl')),    # 使用新函式
                        'major_pct': clean_float(row.get('major_pct')),
                        'note': row.get('note', '')
                    }
                )
                count += 1
                
            messages.success(request, f"成功匯入 {stock_name} ({stock_id}) 共 {count} 筆資料！")
            return redirect(f'/?stock={stock_id}')
            
        except Exception as e:
            # 印出錯誤詳情以便除錯
            import traceback
            print(traceback.format_exc())
            messages.error(request, f"匯入錯誤: {e}")

    # 查詢邏輯 (保持不變)
    query_stock = request.GET.get('stock', '')
    chart_data = {}
    table_data = []
    
    if query_stock:
        qs = StockData.objects.filter(stock_id=query_stock).order_by('date')
        if qs.exists():
            # 取得最新的一筆資料名稱，確保查詢後能顯示名稱
            stock_name_display = qs.first().stock_name
            
            chart_data = {
                'dates': [d.date.strftime('%Y/%m/%d') for d in qs],
                'prices': [d.price for d in qs],
                'major_pcts': [d.major_pct for d in qs]
            }
            table_data = qs.order_by('-date')
        else:
            stock_name_display = query_stock
    else:
        stock_name_display = ""

    return render(request, 'dashboard.html', {
        'chart_data': json.dumps(chart_data),
        'table_data': table_data,
        'query_stock': query_stock,
        'stock_name_display': stock_name_display
    })