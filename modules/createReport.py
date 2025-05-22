from reportlab.pdfgen import canvas
from reportlab.platypus import (SimpleDocTemplate, Paragraph, PageBreak, Image, Spacer, Table, TableStyle)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import inch, A4
from reportlab.graphics.shapes import Drawing, Line
from reportlab.lib.colors import Color
from io import BytesIO
import numpy as np
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
from fuzzywuzzy import process
from typing import List, Union
from src.testInfo import InfoContainer


VALID_TEST_TYPES = ['DSC_OIT', "VICAT", "MFI"]
HOME = os.getcwd()

class FooterCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
        self.width, self.height = A4

    def showPage(self): 
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            if (self._pageNumber > 1):
                self.draw_canvas(page_count)
            else:
                self.draw_header(os.path.join(HOME, 'resources/headerInfo.txt'))
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
    
    def draw_canvas(self, page_count):
        page = "Page %s of %s" % (self._pageNumber, page_count)
        
        self.saveState()
        self.setStrokeColorRGB(0, 0, 0)
        self.setLineWidth(1)
        self.drawImage(os.path.join(HOME, 'resources/logo.png'), self.width-inch*8-5, self.height-50, width=100, height=20, preserveAspectRatio=True)
        self.drawImage(os.path.join(HOME, 'resources/logo2.png'), self.width - inch * 1.5, self.height-50, width=100, height=30, preserveAspectRatio=True, mask='auto')
        self.line(self.width * 0.05, self.height * 0.10, self.width * 0.95, self.height * 0.10)
        self.setFont('Times-Roman', 10)
        self.drawString(self.width * 0.85, self.height * 0.065, page)
        self.restoreState()
        
    def draw_header(self, path):
        img = Image(os.path.join(HOME, 'resources/logo.png'))
        width, height = img.wrap(0, 0)
        aspect_ratio = width / height
            
        img.drawHeight = self.height * 0.07
        img.drawWidth = self.height * 0.07 * aspect_ratio
        
        headerFormat = ParagraphStyle('Helvetica', fontSize=8, leading= 10, justifyBreaks=1, alignment=TA_RIGHT, justifyLastLine=1)
        headerInfo = self.getHeaderInfo(path)
        singles, labels, info = headerInfo

        textBuffer = []
        singlesBuffer = []
        for single in singles:
            text = f"""{single}<br/>"""
            singlesBuffer.append(Paragraph(single, headerFormat))
        
        for label, info in zip(labels, info):
            text = f"""<font color="#b31919">{label}</font>{info}<br/>"""
            textBuffer.append(text)
        
        result = []
        for i in range(0, len(textBuffer), 2):
            if i + 2 <= len(textBuffer):
                result.append([Paragraph(textBuffer[i], headerFormat), Paragraph(textBuffer[i+1], headerFormat)])
        
        infoTable = Table(result, colWidths=[self.width * 0.30, self.width * 0.30])
        infoTable.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), (0, 0, 1)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('HALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        content = [singlesBuffer, infoTable]
        
        header = [
            [img, content]
        ]
        
        headerTable = Table(header, colWidths=[(self.width - 1.5*inch) / 3, (self.width - 1.5*inch) / 3 * 2])
        
        headerTable.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), (0, 0, 1)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('HALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        headerTable.wrapOn(self, width, height)
        headerTable.drawOn(self, inch / 1.2, self.height - inch * 1.2)

    @staticmethod    
    def getHeaderInfo(path):
        try:
            headerInfoPath = path
            info = []
            labels = []
            singles = []
            with open(headerInfoPath, 'r') as file: 
                lines = file.readlines()
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if i == 0:
                        singles.append(line)
                        continue
                    
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        before_colon, after_colon = parts
                        info.append(after_colon)
                        labels.append(before_colon + ":")
                    else:
                        singles.append(parts)
            
            return singles, labels, info
        except FileNotFoundError:
            print(f"Error: The file {headerInfoPath} does not exist.")
        except Exception as e:
            print(f"An error occurred: {e}")
        
class ReportCreator():
    def __init__(self, filename="default.pdf", testType='None', test_db=None, test_ID=None, line_num=None):
        self.styleSheet = getSampleStyleSheet()
        self.elements = []
        reportsPath = os.path.join(HOME, 'reports')

        
        
        if self.isValidDataBase(test_db):
            self.testDataBase = test_db
        else:
            raise TypeError("Invalid Database File.")
        
        if isinstance(test_ID, int):
            self.testID = test_ID
        else:
            raise TypeError("Invalid Test ID.")
        
        predictedTestType = self.isValidTestType(testType)
        if predictedTestType is not None:
            self.testType = predictedTestType
        else:
            raise ValueError("Test Type is not valid.")

        if self.testType.lower() == 'vicat':
            if isinstance(line_num, int):
                if line_num > 0 and line_num <= 5:
                    self.lineNum = line_num
                else:
                    raise ValueError("Line number argument is invalid for this test type.")
            else:
                raise TypeError("Inappropriate line number argument, an integer withing 1-5 range is necessary for VICAT.")
        
        if self.isValidFileName(filename):
            if not os.path.exists(reportsPath):
                os.makedirs(reportsPath)                
            self.filepath = os.path.join(reportsPath, filename)
        else:
            raise TypeError("Invalid Filename (Extension).")
            
        self.width, self.height = A4

        self.firstPage()
        self.nextPagesHeader(True)
        self.testInfoPage(self.testType)
        
        self.doc = SimpleDocTemplate(self.filepath, pagesize=A4)
        self.doc.multiBuild(self.elements, canvasmaker=FooterCanvas)
                
    def firstPage(self):
        spacer = Spacer(10, self.height*0.1)
        self.elements.append(spacer)
        
        img = Image(os.path.join(HOME, 'resources/logo2.png'))
        width, height = img.wrap(0, 0)
        aspect_ratio = width / height
        img.drawHeight = self.height * 0.4
        img.drawWidth = self.height * 0.4 * aspect_ratio
        
        self.elements.append(img)

        spacer = Spacer(10, self.height * 0.2)
        self.elements.append(spacer)

        # PLACEHOLDER PARAGRAPH
        textFormat = ParagraphStyle('Helvetica', fontSize=9, leading=14, justifyBreaks=1, alignment=TA_LEFT, justifyLastLine=1)
        text = """PLACEHOLDER PARAGRAPH<br/>
        """
        paragraphReportSummary = Paragraph(text, textFormat)
        self.elements.append(paragraphReportSummary)
        self.elements.append(PageBreak())
    
    def nextPagesHeader(self, isSecondPage=False):
        if isSecondPage:
            psHeaderText = ParagraphStyle('Helvetica', fontSize=16, alignment=TA_CENTER, borderWidth=3, textColor=Color((0.0/255), (0.0/255), (0.0/255), 1))
            text = 'ALARGE TEST RAPORU'
            paragraphReportHeader = Paragraph(text, psHeaderText)
            self.elements.append(paragraphReportHeader)
            
            spacer = Spacer(10, 12)
            self.elements.append(spacer)
            
            d = Drawing(500, 1)
            line = Line(-40, 0, 485, 0)
            line.strokeColor = Color((0.0/255), (0.0/255), (0.0/255), 1)
            line.strokeWidth = 1
            d.add(line)
            self.elements.append(d)
            
            spacer = Spacer(10, 5)
            self.elements.append(spacer)
            
    def testInfoPage(self, testType='None'):
        dataFrame = self.getTestInfo(self.testDataBase)
        
        if testType.lower() == 'dsc_oit':
            test_DataFrame  = pd.DataFrame(dataFrame['TestAna'])
            test_DataFrame2  = pd.DataFrame(dataFrame['testDetay'])
            
            filteredTestAna = test_DataFrame[test_DataFrame['TestId'] == self.testID]
            filteredTestAna.columns = filteredTestAna.columns.str.lower()
            
            filteredTestDetay = test_DataFrame2[test_DataFrame2['TestId'] == self.testID]
            filteredTestDetay.columns = filteredTestDetay.columns.str.lower()
    
            testInfo = InfoContainer(testType)
            table = self.prepareInfoTable(filteredTestAna, testInfo.labels1, testInfo.labels2, testInfo.data1List, testInfo.data2List)
            self.elements.append(table)
            
            spacer = Spacer(10, 10)
            self.elements.append(spacer)
            
            d = Drawing(500, 1)
            line = Line(-40, 0, 485, 0)
            line.strokeColor = Color((0.0/255), (0.0/255), (0.0/255), 1)
            line.strokeWidth = 0.5
            d.add(line)
            self.elements.append(d)
            
            # Plots
            indexes = ["numunesicakligi", "referanssicakligi", "watt"]
            data = []
            x = filteredTestDetay['testsuresi'].values
            
            for column in filteredTestDetay.columns:
                if column in indexes:
                    y = filteredTestDetay[f'{column}'].values
                    label = column
                    dataset = [label, x, y]
                    data.append(dataset)
                    
            self.addPlot(data[0:2], drawingWidth=self.width*0.6, drawingHeight=self.height*0.2, title='Sıcaklık-Zaman Grafiği', xAxis='Zaman [sn]', yAxis='Sıcaklık [°C]')
            self.addPlot(data[2:], drawingWidth=self.width*0.6, drawingHeight=self.height*0.2, title='Isı-Zaman Grafiği', xAxis='Zaman [sn]', yAxis='Isı [Watt]')
            
            x = filteredTestDetay['numunesicakligi'].values
            y = filteredTestDetay['watt'].values
            label = 'Isı'
            
            dataset = [label, x, y]
            data = []
            data.append(dataset)
            
            self.addPlot(data, drawingWidth=self.width*0.6, drawingHeight=self.height*0.2, title='Isı-Sıcaklık Grafiği', xAxis='Sıcaklık [°C]', yAxis='Isı [Watt]')
        elif testType.lower() == 'mfi':
            test_DataFrame  = pd.DataFrame(dataFrame['TestAna'])
            test_DataFrame2  = pd.DataFrame(dataFrame['TestDetay'])
            
            filteredTestAna = test_DataFrame[test_DataFrame['TestId'] == self.testID]
            filteredTestAna.columns = filteredTestAna.columns.str.lower()
        
            filteredTestDetay = test_DataFrame2[test_DataFrame2['Detay_TestId'] == self.testID]
            filteredTestDetay.columns = filteredTestDetay.columns.str.lower()

            testInfo = InfoContainer(testType)
            table = self.prepareInfoTable(filteredTestAna, testInfo.labels1, testInfo.labels2, testInfo.data1List, testInfo.data2List)
            self.elements.append(table)
            
            spacer = Spacer(10, 10)
            self.elements.append(spacer)
            
            d = Drawing(500, 1)
            line = Line(-40, 0, 485, 0)
            line.strokeColor = Color((0.0/255), (0.0/255), (0.0/255), 1)
            line.strokeWidth = 0.5
            d.add(line)
            self.elements.append(d)
            
            # Table
            indexes = ['detay_id', 'detay_kesmezamani', 'detay_agirlik', 'detay_mvr', 'detay_mfr']
            headerLabels = ['No', 'Agirlik (gr)', 'Kesme Zam. (sn)', 'MVR (mm³/10dk)', 'MFR (gr/10dk)']
            data = []
            
            for column in filteredTestDetay.columns:
                if column in indexes:
                    y = filteredTestDetay[f'{column}'].values
                    data.append(y)
                    
            self.addTable(data, headerLabels, tableWidth=self.width*0.8, colRatios=[3, 5, 8, 8, 8])
        elif testType.lower() == 'vicat':
            test_DataFrame  = pd.DataFrame(dataFrame['Test_Ana'])
            test_DataFrame2 = pd.DataFrame(dataFrame['Test_Ana_Hat'])
            test_DataFrame3 = pd.DataFrame(dataFrame['Test_Detay'])
            
            filteredTestAna = test_DataFrame[test_DataFrame['Test_Id'] == self.testID]
            filteredTestAna.columns = filteredTestAna.columns.str.lower()
            
            filteredTestAnaHat = test_DataFrame2[test_DataFrame2['Test_Id'] == self.testID]
            filteredTestAnaHat = filteredTestAnaHat[filteredTestAnaHat['Hat_Num'] == self.lineNum]
            filteredTestAnaHat.columns = filteredTestAnaHat.columns.str.lower()
                    
            filteredTestAnaHat = filteredTestAnaHat.drop(filteredTestAnaHat.columns[0], axis=1)
            filteredConcatTestAna = pd.concat([filteredTestAna.reset_index(drop=True), filteredTestAnaHat.reset_index(drop=True)], axis=1)

            filteredTestDetay = test_DataFrame3[test_DataFrame3['Test_Id'] == self.testID]
            filteredTestDetay = filteredTestDetay[filteredTestDetay['Hat_Numarasi'] == self.lineNum]
            filteredTestDetay.columns = filteredTestDetay.columns.str.lower()
            
            finalTemp = filteredTestDetay['sıcaklık'].iloc[-1]
            
            filteredConcatTestAna['son_sicaklik'] = finalTemp
            
            testInfo = InfoContainer(testType)
            table = self.prepareInfoTable(filteredConcatTestAna, testInfo.labels1, testInfo.labels2, testInfo.data1List, testInfo.data2List)
            self.elements.append(table)
            
            spacer = Spacer(10, 10)
            self.elements.append(spacer)
            
            d = Drawing(500, 1)
            line = Line(-40, 0, 485, 0)
            line.strokeColor = Color((0.0/255), (0.0/255), (0.0/255), 1)
            line.strokeWidth = 0.5
            d.add(line)
            self.elements.append(d)
            
            #Plot
            indexes = ["batma"]
            data = []
            x = filteredTestDetay['sıcaklık'].values
            
            for column in filteredTestDetay.columns:
                if column in indexes:
                    y = filteredTestDetay[f'{column}'].values
                    label = column
                    dataset = [label, x, y]
                    data.append(dataset)
                    
            self.addPlot(data, drawingWidth=self.width*0.6, drawingHeight=self.height*0.2, title='Sıcaklık-Batma Grafiği', xAxis='Batma [mm]', yAxis='Sıcaklık [°C]')
            
            dataset = [label, x, y]
            data = []
            data.append(dataset)
            
        else: 
            raise Exception("Invalid Test Type.")
            
    def getTestInfo(self, path): # AAA---------------------------------------------------------------------------
        try:
            with sqlite3.connect(path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cur.fetchall()
                if len(tables) > 0:
                    data_frames = {}
                    for table in tables:
                        table_name = table[0]
                        cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                        row_count = cur.fetchone()[0]
                        if row_count > 0:
                            for table in tables:
                                table_name = table[0]
                                df = pd.read_sql_query(f"SELECT * FROM {table_name};", conn)
                                data_frames[table_name] = df
                            return data_frames   
                    else:
                        print("Empty Database.")
                else:
                    print("Empty Database.")
        except sqlite3.Error as e:
            print(e)
            
    def addPlot(self, data, drawingWidth=400, drawingHeight=200, title="Title", xAxis="X Axis", yAxis="Y Axis"):
        spacer = Spacer(0, 10)
        self.elements.append(spacer)
        
        buf = BytesIO()
        
        plt.figure(figsize=(drawingWidth*0.03, drawingHeight*0.03))
        
        for dataset in data:
            label, x, y = dataset
            plt.plot(x, y, label=label)
                
        plt.title(title)
        plt.xlabel(xAxis)
        plt.ylabel(yAxis)
        plt.grid(color='gray', linestyle='dashdot', linewidth=1)
        plt.legend()
        
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        
        buf.seek(0)
        
        plot_image = Image(buf, width=drawingWidth, height=drawingHeight)
        
        self.elements.append(plot_image)
        
        spacer = Spacer(0, 5)
        self.elements.append(spacer)
        
        d = Drawing(500, 1)
        line = Line(0, 0, 445, 0)
        line.strokeColor = Color((0.0/255), (0.0/255), (0.0/255), 1)
        line.strokeWidth = 0.5
        d.add(line)
        self.elements.append(d)
        
    def addTable(self, data, headerLabels, createAverage=False, tableWidth=400, colRatios='Equal'):
        spacer = Spacer(0, 10)
        self.elements.append(spacer)
        
        tableData = [list(row) for row in zip(*data)]
        tableData = [headerLabels] + tableData
        
        colWidths = []
        rowHeights = []
        
        if colRatios == 'Equal':
            for _ in range(len(tableData[0])):
                colWidths.append(tableWidth/len(tableData[0]))
        elif isinstance(colRatios, list):
            widths = self.calculateTableColWidths(colRatios, tableWidth)
            if len(colRatios) == len(tableData[0] and widths):
                colWidths = widths
            else:
                colWidths.append(tableWidth/len(tableData[0]))
        
        rowHeight = self.height * 0.03
        
        for i in range(len(tableData)):
            if i == 0:
                rowHeights.append(rowHeight * 1.5)
            else:
                rowHeights.append(rowHeight)
            
        table = Table(tableData, colWidths=colWidths, rowHeights=rowHeights)
        
        bgColor = (255.0/255, 255.0/255, 255.0/255)
        bgColor2 = self.darkenColor(bgColor, 0.07)
        bgColor3 = self.darkenColor(bgColor2, 0.03)
        
        table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), (0, 0, 0)),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('HALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, 0), bgColor3),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [bgColor, bgColor2]),
            ('INNERGRID', (0,0), (-1,-1), 0.25, (0, 0, 0)),
            ('BOX', (0,0), (-1,-1), 0.25, (0, 0, 0)),
            ]))
        
        self.elements.append(table)
        
        spacer = Spacer(0, 5)
        self.elements.append(spacer)
        
        d = Drawing(500, 1)
        line = Line(0, 0, 445, 0)
        line.strokeColor = Color((0.0/255), (0.0/255), (0.0/255), 1)
        line.strokeWidth = 0.5
        d.add(line)
        self.elements.append(d)
            
    @staticmethod
    def prepareInfoTable(db, labels1, labels2, data1List, data2List):
        data1 = []
        data2 = []

        for label in data1List:
            label = label.lower()
            if label in db:
                if isinstance(db[f"{label}"].values, np.ndarray) and len(db[f"{label}"].values) > 0:
                    val = str(db[f"{label}"].values[0])
                    if len(val) > 0 and val.lower() != 'nan':
                        data1.append(val)
                    else:
                        data1.append('-')
                else:
                    data1.append('-')
            else:
                data2.append('-')
                
        for label in data2List:
            label = label.lower()
            if label in db:
                if isinstance(db[f"{label}"].values, np.ndarray) and len(db[f"{label}"].values) > 0:
                    val = str(db[f"{label}"].values[0])
                    if len(val) > 0 and val.lower() != 'nan':
                        data2.append(val)
                    else:
                        data2.append('-')
                else:
                    data2.append('-')
            else:
                data2.append('-')
        
        styles = getSampleStyleSheet()
        bold_style = ParagraphStyle(name='BoldStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_LEFT)
        normal_style = ParagraphStyle(name='NormalStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_LEFT)
        
        table_data = []
        for l1, d1, l2, d2 in zip(labels1, data1, labels2, data2):
            table_data.append([
                Paragraph(l1, bold_style),
                Paragraph(d1, normal_style),
                Paragraph(l2, bold_style),
                Paragraph(d2, normal_style)
            ])
            
        table = Table(table_data,
                      rowHeights=20,
                      )
        
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), (1, 1, 1)),
            ('TEXTCOLOR', (0, 0), (-1, -1), (0, 0, 1)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('HALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10)
        ])
        
        table.setStyle(table_style)
        return table
    
    @staticmethod
    def calculateTableColWidths(ratios: List[Union[int, float]], width: (int, float)) -> List[float]:
        if not ratios:
            return False
        
        if not all(isinstance(num, (int, float)) for num in ratios):
            raise TypeError("All elements for table column ratios must be integers or floats.")
        
        if not all(num > 0 for num in ratios):
            raise ValueError("All elements for table column ratios must be positive numbers.")
    
        totalSum = sum(ratios)
        
        columnWidths = [num / totalSum * width for num in ratios]
        return columnWidths
     
    @staticmethod
    def darkenColor(color, percentage):
        def hex2Rgb(hex_color):
            """Converts HEX color to RGB tuple."""
            hex_color = hex_color.lstrip('#')
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return (r / 255, g / 255, b / 255)
    
        def darkenRgb(r, g, b, percentage):
            """Darkens the RGB color."""
            return (r * (1 - percentage), g * (1 - percentage), b * (1 - percentage))

        if isinstance(color, str):
            # Handle HEX color input
            color = hex2Rgb(color)
        elif isinstance(color, tuple) and len(color) == 3:
            # Handle RGB color input
            r, g, b = color
            if r > 1 or g > 1 or b > 1:
                raise ValueError("RGB values should be normalized to the 0-1 range.")
        else:
            raise ValueError("Invalid color format. Please provide a HEX color or an RGB tuple.")
    
        r, g, b = color
        r, g, b = darkenRgb(r, g, b, percentage)
    
        return (r, g, b)
    
    @staticmethod
    def isValidDataBase(filePath: str) -> bool:
        validExt = ['.sqlite', '.db', '.sql']
        return os.path.splitext(filePath)[1] in validExt
    
    @staticmethod
    def isValidFileName(filePath: str) -> bool:
        validExt = ['.pdf']
        return os.path.splitext(filePath)[1] in validExt
    
    @staticmethod
    def isValidTestType(testType: str):
        testType = testType.strip().upper()
        
        if testType in VALID_TEST_TYPES:
            return testType
        
        closest_match, score = process.extractOne(testType, VALID_TEST_TYPES)

        THRESHOLD = 80
        if score >= THRESHOLD:
            return closest_match
        else:
            return None
    

if __name__ == "__main__":
    # ReportCreator("DSC_OIT_ÖrnekRapor.pdf", testType='DSC_OIT', test_db="DSC-OIT ornekVeri Tabani.db", test_ID=142)
    # ReportCreator("MFI_ÖrnekRapor.pdf", testType='MFI', test_db="MFI ornekVeri Tabani.db", test_ID=564)
    ReportCreator("VICAT_ÖrnekRapor.pdf", testType='VICAT', test_db="VICAT ornekVeri Tabani.db", test_ID=1, line_num=1)