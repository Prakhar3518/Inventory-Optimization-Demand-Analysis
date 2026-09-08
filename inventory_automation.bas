Attribute VB_Name = "InventoryAutomation"
'==============================================================================
' InventoryAutomation
' Inventory Optimization & Demand Analysis
'------------------------------------------------------------------------------
' Two macros that automate the repetitive part of the monthly reporting cycle.
'
'   1) ConsolidateMonthlyFiles  - reads every monthly CSV extract in a chosen
'                                 folder and stacks them into one Master_Data
'                                 sheet, tagging each row with its source file.
'
'   2) BuildActionRegister      - reads Master_Data, computes days of cover per
'                                 store-product for the latest date, classifies
'                                 each position, and writes a formatted,
'                                 sorted action list to Action_Register.
'
' WHERE THIS CODE GOES
'   Open inventory_analysis.xlsx, press Alt+F11 to open the VBA editor, then
'   File > Import File... and select this .bas file. It arrives as a module
'   named InventoryAutomation. Save the workbook as .xlsm, because .xlsx
'   cannot store macros. Run either macro with Alt+F8.
'
' EXPECTED INPUT
'   One CSV per month in a single folder. Each must carry the source column
'   headers in row 1:
'     Date, Store ID, Product ID, Category, Region, Inventory Level,
'     Units Sold, Units Ordered, Demand Forecast, Price, Discount,
'     Weather Condition, Holiday/Promotion, Competitor Pricing, Seasonality
'
' POLICY THRESHOLDS
'   Read from the Parameters sheet (B5, B6, B7) so the macro and the worksheet
'   formulas can never disagree. Defaults apply if that sheet is missing.
'==============================================================================

Option Explicit

Private Const MASTER_SHEET As String = "Master_Data"
Private Const ACTION_SHEET As String = "Action_Register"
Private Const PARAM_SHEET As String = "Parameters"
Private Const EXPECTED_COLS As Long = 15

'==============================================================================
' MACRO 1 - Consolidate monthly extracts into one master sheet
'==============================================================================
Public Sub ConsolidateMonthlyFiles()

    Dim folderPath As String
    Dim fileName As String
    Dim wsMaster As Worksheet
    Dim wbSource As Workbook
    Dim wsSource As Worksheet
    Dim nextRow As Long, lastRow As Long, lastCol As Long
    Dim filesLoaded As Long, rowsLoaded As Long
    Dim startTime As Single

    startTime = Timer

    ' --- Ask the user for the folder holding the monthly extracts -------------
    With Application.FileDialog(msoFileDialogFolderPicker)
        .Title = "Select the folder containing the monthly inventory extracts"
        If .Show <> -1 Then
            MsgBox "Cancelled. No files were imported.", vbInformation
            Exit Sub
        End If
        folderPath = .SelectedItems(1)
    End With
    If Right$(folderPath, 1) <> Application.PathSeparator Then
        folderPath = folderPath & Application.PathSeparator
    End If

    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    On Error GoTo CleanFail

    ' --- Start from a clean master sheet -------------------------------------
    Set wsMaster = GetOrCreateSheet(MASTER_SHEET)
    wsMaster.Cells.Clear

    ' --- Loop every CSV in the folder ----------------------------------------
    fileName = Dir(folderPath & "*.csv")
    Do While Len(fileName) > 0

        Set wbSource = Workbooks.Open(fileName:=folderPath & fileName, ReadOnly:=True)
        Set wsSource = wbSource.Sheets(1)

        lastRow = wsSource.Cells(wsSource.Rows.Count, 1).End(xlUp).Row
        lastCol = wsSource.Cells(1, wsSource.Columns.Count).End(xlToLeft).Column

        ' Skip a file whose shape does not match, rather than silently
        ' corrupting the master sheet with misaligned columns.
        If lastCol <> EXPECTED_COLS Or lastRow < 2 Then
            wbSource.Close SaveChanges:=False
            Debug.Print "SKIPPED (unexpected shape): " & fileName
            fileName = Dir
            GoTo NextFile
        End If

        If filesLoaded = 0 Then
            ' First file supplies the header row, plus one extra column so we
            ' can always trace a row back to the file it came from.
            wsSource.Range(wsSource.Cells(1, 1), wsSource.Cells(1, lastCol)).Copy
            wsMaster.Range("A1").PasteSpecial xlPasteValues
            wsMaster.Cells(1, lastCol + 1).Value = "Source File"
            nextRow = 2
        End If

        wsSource.Range(wsSource.Cells(2, 1), wsSource.Cells(lastRow, lastCol)).Copy
        wsMaster.Cells(nextRow, 1).PasteSpecial xlPasteValues
        wsMaster.Range(wsMaster.Cells(nextRow, lastCol + 1), _
                       wsMaster.Cells(nextRow + lastRow - 2, lastCol + 1)).Value = fileName

        nextRow = nextRow + lastRow - 1
        rowsLoaded = rowsLoaded + lastRow - 1
        filesLoaded = filesLoaded + 1

        wbSource.Close SaveChanges:=False
        fileName = Dir

NextFile:
    Loop

    Application.CutCopyMode = False

    If filesLoaded = 0 Then
        MsgBox "No usable CSV files were found in:" & vbCrLf & folderPath, vbExclamation
        GoTo CleanExit
    End If

    ' --- Clean the consolidated data -----------------------------------------
    CleanMasterData wsMaster
    FormatMasterData wsMaster

    MsgBox "Consolidation complete." & vbCrLf & vbCrLf & _
           "Files imported: " & filesLoaded & vbCrLf & _
           "Rows imported:  " & Format(rowsLoaded, "#,##0") & vbCrLf & _
           "Rows after cleaning: " & Format(wsMaster.Cells(wsMaster.Rows.Count, 1).End(xlUp).Row - 1, "#,##0") & vbCrLf & _
           "Elapsed: " & Format(Timer - startTime, "0.0") & " seconds", _
           vbInformation, "Master_Data refreshed"

CleanExit:
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
    Exit Sub

CleanFail:
    MsgBox "Import failed on file: " & fileName & vbCrLf & vbCrLf & _
           "Error " & Err.Number & ": " & Err.Description, vbCritical
    On Error Resume Next
    If Not wbSource Is Nothing Then wbSource.Close SaveChanges:=False
    Resume CleanExit

End Sub

'------------------------------------------------------------------------------
' Cleaning applied to the consolidated sheet:
'   - trim stray whitespace from the text key columns
'   - coerce the Date column to a real date
'   - drop rows duplicated on Date + Store ID + Product ID
'   - drop rows missing a key value
'------------------------------------------------------------------------------
Private Sub CleanMasterData(ws As Worksheet)

    Dim lastRow As Long, i As Long
    Dim removed As Long

    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow < 2 Then Exit Sub

    ' Trim text columns: Store ID, Product ID, Category, Region
    Dim c As Variant
    For Each c In Array(2, 3, 4, 5)
        With ws.Range(ws.Cells(2, c), ws.Cells(lastRow, c))
            .Value = Application.Evaluate("IF(ROW(" & .Address & "),TRIM(" & .Address & "))")
        End With
    Next c

    ' Force column A to a genuine date serial. Text dates break every
    ' downstream date calculation, and CSV imports produce them constantly.
    For i = 2 To lastRow
        If Not IsEmpty(ws.Cells(i, 1).Value) Then
            If Not IsDate(ws.Cells(i, 1).Value) Then
                ws.Cells(i, 1).Value = ""
            Else
                ws.Cells(i, 1).Value = CDate(ws.Cells(i, 1).Value)
            End If
        End If
    Next i
    ws.Range(ws.Cells(2, 1), ws.Cells(lastRow, 1)).NumberFormat = "yyyy-mm-dd"

    ' Remove rows missing any part of the composite key
    For i = lastRow To 2 Step -1
        If Len(Trim$(CStr(ws.Cells(i, 1).Value))) = 0 _
           Or Len(Trim$(CStr(ws.Cells(i, 2).Value))) = 0 _
           Or Len(Trim$(CStr(ws.Cells(i, 3).Value))) = 0 Then
            ws.Rows(i).Delete
            removed = removed + 1
        End If
    Next i

    ' De-duplicate on Date + Store ID + Product ID, the true grain
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    ws.Range(ws.Cells(1, 1), ws.Cells(lastRow, EXPECTED_COLS + 1)).RemoveDuplicates _
        Columns:=Array(1, 2, 3), Header:=xlYes

    Debug.Print "CleanMasterData: removed " & removed & " incomplete rows"

End Sub

'------------------------------------------------------------------------------
' Presentation formatting for the master sheet
'------------------------------------------------------------------------------
Private Sub FormatMasterData(ws As Worksheet)

    Dim lastRow As Long, lastCol As Long

    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    If lastRow < 2 Then Exit Sub

    With ws.Range(ws.Cells(1, 1), ws.Cells(lastRow, lastCol))
        .Font.Name = "Arial"
        .Font.Size = 10
        .Borders.LineStyle = xlContinuous
        .Borders.Color = RGB(191, 191, 191)
    End With

    With ws.Range(ws.Cells(1, 1), ws.Cells(1, lastCol))
        .Font.Bold = True
        .Font.Color = RGB(255, 255, 255)
        .Interior.Color = RGB(31, 56, 100)
        .HorizontalAlignment = xlCenter
    End With

    ws.Range(ws.Cells(1, 1), ws.Cells(lastRow, lastCol)).Columns.AutoFit
    ws.Rows(1).AutoFilter
    ws.Activate
    ActiveWindow.FreezePanes = False
    ws.Range("A2").Select
    ActiveWindow.FreezePanes = True

End Sub

'==============================================================================
' MACRO 2 - Build the action register for the latest date in Master_Data
'
' For every store-product it computes:
'   average daily demand  (mean units sold across the whole master sheet)
'   days of cover         (latest inventory / average daily demand)
'   stock status          (Critical / Below Reorder / Healthy / Excess)
'   order quantity        (units needed to reach target cover)
' then writes the result sorted with the most urgent positions first.
'==============================================================================
Public Sub BuildActionRegister()

    Dim wsMaster As Worksheet, wsOut As Worksheet
    Dim lastRow As Long, i As Long, outRow As Long
    Dim latestDate As Date
    Dim critDays As Double, reorderDays As Double, targetDays As Double

    Dim demandSum As Object, demandCount As Object
    Dim latestInv As Object, latestOrdered As Object, latestPrice As Object
    Dim key As Variant

    On Error GoTo CleanFail
    Application.ScreenUpdating = False

    Set wsMaster = ThisWorkbook.Sheets(MASTER_SHEET)
    lastRow = wsMaster.Cells(wsMaster.Rows.Count, 1).End(xlUp).Row
    If lastRow < 2 Then
        MsgBox "Master_Data is empty. Run ConsolidateMonthlyFiles first.", vbExclamation
        GoTo CleanExit
    End If

    ' Thresholds come from the Parameters sheet so the macro and the worksheet
    ' formulas always use the same policy.
    critDays = GetParameter("B5", 1#)
    reorderDays = GetParameter("B6", 1.5)
    targetDays = GetParameter("B7", 3#)

    Set demandSum = CreateObject("Scripting.Dictionary")
    Set demandCount = CreateObject("Scripting.Dictionary")
    Set latestInv = CreateObject("Scripting.Dictionary")
    Set latestOrdered = CreateObject("Scripting.Dictionary")
    Set latestPrice = CreateObject("Scripting.Dictionary")

    ' Read the whole sheet into an array once. Looping cells directly on
    ' 70,000+ rows is minutes slower.
    Dim data As Variant
    data = wsMaster.Range(wsMaster.Cells(2, 1), wsMaster.Cells(lastRow, EXPECTED_COLS)).Value

    ' Pass 1 - find the latest date present
    For i = 1 To UBound(data, 1)
        If IsDate(data(i, 1)) Then
            If CDate(data(i, 1)) > latestDate Then latestDate = CDate(data(i, 1))
        End If
    Next i

    ' Pass 2 - accumulate demand, and capture the latest-date snapshot
    Dim skuKey As String
    For i = 1 To UBound(data, 1)
        If IsDate(data(i, 1)) Then
            skuKey = CStr(data(i, 2)) & "-" & CStr(data(i, 3))

            demandSum(skuKey) = demandSum(skuKey) + CDbl(data(i, 7))    ' Units Sold
            demandCount(skuKey) = demandCount(skuKey) + 1

            If CDate(data(i, 1)) = latestDate Then
                latestInv(skuKey) = CDbl(data(i, 6))                    ' Inventory Level
                latestOrdered(skuKey) = CDbl(data(i, 8))                ' Units Ordered
                latestPrice(skuKey) = CDbl(data(i, 10))                 ' Price
            End If
        End If
    Next i

    ' --- Write the register ---------------------------------------------------
    Set wsOut = GetOrCreateSheet(ACTION_SHEET)
    wsOut.Cells.Clear

    wsOut.Range("A1").Value = "Action Register - position as at " & Format(latestDate, "yyyy-mm-dd")
    wsOut.Range("A1").Font.Size = 14
    wsOut.Range("A1").Font.Bold = True
    wsOut.Range("A2").Value = "Thresholds (days of cover): critical < " & critDays & _
                              " | reorder < " & reorderDays & " | target " & targetDays
    wsOut.Range("A2").Font.Italic = True

    Dim headers As Variant
    headers = Array("SKU Key", "Store ID", "Product ID", "Inventory (units)", _
                    "Avg Daily Demand", "Days of Cover", "Order Qty to Target", _
                    "Units Ordered", "Order Gap", "Inventory Value", _
                    "Stock Status", "Recommended Action")
    For i = 0 To UBound(headers)
        wsOut.Cells(4, i + 1).Value = headers(i)
    Next i

    outRow = 5
    Dim adr As Double, cover As Double, orderQty As Double, status As String

    For Each key In latestInv.Keys
        adr = 0
        If demandCount(key) > 0 Then adr = demandSum(key) / demandCount(key)

        cover = 0
        If adr > 0 Then cover = latestInv(key) / adr

        orderQty = adr * targetDays - latestInv(key)
        If orderQty < 0 Then orderQty = 0

        If cover < critDays Then
            status = "Critical"
        ElseIf cover < reorderDays Then
            status = "Below Reorder"
        ElseIf cover <= targetDays Then
            status = "Healthy"
        Else
            status = "Excess"
        End If

        wsOut.Cells(outRow, 1).Value = key
        wsOut.Cells(outRow, 2).Value = Split(key, "-")(0)
        wsOut.Cells(outRow, 3).Value = Split(key, "-")(1)
        wsOut.Cells(outRow, 4).Value = latestInv(key)
        wsOut.Cells(outRow, 5).Value = Round(adr, 2)
        wsOut.Cells(outRow, 6).Value = Round(cover, 2)
        wsOut.Cells(outRow, 7).Value = Round(orderQty, 0)
        wsOut.Cells(outRow, 8).Value = latestOrdered(key)
        wsOut.Cells(outRow, 9).Value = Round(latestOrdered(key) - orderQty, 0)
        wsOut.Cells(outRow, 10).Value = Round(latestInv(key) * latestPrice(key), 2)
        wsOut.Cells(outRow, 11).Value = status
        wsOut.Cells(outRow, 12).Value = ActionFor(status)

        outRow = outRow + 1
    Next key

    FormatActionRegister wsOut, outRow - 1

    MsgBox "Action register built for " & Format(latestDate, "yyyy-mm-dd") & "." & vbCrLf & vbCrLf & _
           "Positions listed: " & (outRow - 5) & vbCrLf & _
           "Critical: " & Application.WorksheetFunction.CountIf(wsOut.Columns(11), "Critical") & vbCrLf & _
           "Below Reorder: " & Application.WorksheetFunction.CountIf(wsOut.Columns(11), "Below Reorder") & vbCrLf & _
           "Excess: " & Application.WorksheetFunction.CountIf(wsOut.Columns(11), "Excess"), _
           vbInformation, "Action_Register refreshed"

CleanExit:
    Application.ScreenUpdating = True
    Exit Sub

CleanFail:
    MsgBox "Could not build the action register." & vbCrLf & vbCrLf & _
           "Error " & Err.Number & ": " & Err.Description, vbCritical
    Resume CleanExit

End Sub

'------------------------------------------------------------------------------
' Formatting and sort for the action register
'------------------------------------------------------------------------------
Private Sub FormatActionRegister(ws As Worksheet, lastRow As Long)

    If lastRow < 5 Then Exit Sub

    With ws.Range(ws.Cells(4, 1), ws.Cells(lastRow, 12))
        .Font.Name = "Arial"
        .Font.Size = 10
        .Borders.LineStyle = xlContinuous
        .Borders.Color = RGB(191, 191, 191)
    End With

    With ws.Range(ws.Cells(4, 1), ws.Cells(4, 12))
        .Font.Bold = True
        .Font.Color = RGB(255, 255, 255)
        .Interior.Color = RGB(31, 56, 100)
        .HorizontalAlignment = xlCenter
        .WrapText = True
    End With

    ws.Range(ws.Cells(5, 4), ws.Cells(lastRow, 4)).NumberFormat = "#,##0"
    ws.Range(ws.Cells(5, 5), ws.Cells(lastRow, 6)).NumberFormat = "#,##0.00"
    ws.Range(ws.Cells(5, 7), ws.Cells(lastRow, 9)).NumberFormat = "#,##0"
    ws.Range(ws.Cells(5, 10), ws.Cells(lastRow, 10)).NumberFormat = "$#,##0"

    ' Most urgent first: sort ascending on days of cover
    With ws.Sort
        .SortFields.Clear
        .SortFields.Add key:=ws.Range(ws.Cells(5, 6), ws.Cells(lastRow, 6)), Order:=xlAscending
        .SetRange ws.Range(ws.Cells(5, 1), ws.Cells(lastRow, 12))
        .Header = xlNo
        .Apply
    End With

    ' Colour the status column so the exceptions are visible at a glance
    Dim i As Long
    For i = 5 To lastRow
        Select Case ws.Cells(i, 11).Value
            Case "Critical"
                ws.Cells(i, 11).Interior.Color = RGB(255, 199, 206)
                ws.Cells(i, 11).Font.Color = RGB(156, 0, 6)
            Case "Below Reorder"
                ws.Cells(i, 11).Interior.Color = RGB(255, 235, 156)
                ws.Cells(i, 11).Font.Color = RGB(156, 101, 0)
            Case "Healthy"
                ws.Cells(i, 11).Interior.Color = RGB(198, 239, 206)
                ws.Cells(i, 11).Font.Color = RGB(0, 97, 0)
            Case "Excess"
                ws.Cells(i, 11).Interior.Color = RGB(217, 217, 217)
                ws.Cells(i, 11).Font.Color = RGB(64, 64, 64)
        End Select
    Next i

    ws.Range(ws.Cells(4, 1), ws.Cells(lastRow, 12)).Columns.AutoFit
    ws.Rows(4).AutoFilter

End Sub

'==============================================================================
' Helpers
'==============================================================================
Private Function GetOrCreateSheet(sheetName As String) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(sheetName)
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = sheetName
    End If
    Set GetOrCreateSheet = ws
End Function

' Reads a threshold from the Parameters sheet, falling back to a default if
' that sheet or cell is unavailable.
Private Function GetParameter(cellRef As String, defaultValue As Double) As Double
    Dim v As Variant
    On Error GoTo UseDefault
    v = ThisWorkbook.Sheets(PARAM_SHEET).Range(cellRef).Value
    If IsNumeric(v) And Not IsEmpty(v) Then
        GetParameter = CDbl(v)
        Exit Function
    End If
UseDefault:
    GetParameter = defaultValue
End Function

Private Function ActionFor(status As String) As String
    Select Case status
        Case "Critical":      ActionFor = "REPLENISH NOW"
        Case "Below Reorder": ActionFor = "REPLENISH"
        Case "Healthy":       ActionFor = "MAINTAIN"
        Case "Excess":        ActionFor = "REDUCE STOCK"
        Case Else:            ActionFor = "REVIEW"
    End Select
End Function
