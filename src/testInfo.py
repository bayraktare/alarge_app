class InfoContainer():
    def __init__(self, testType='None'):
        self.testType = testType
        self.labels1 = []
        self.labels2 = []
        self.data1List = []
        self.data2List = []
        try:
            if self.testType == 'DSC_OIT':
                self.setInfo(DSC_OIT_Info())
            elif self.testType == 'MFI':
                self.setInfo(MFI_Info()) 
            elif self.testType == 'VICAT':
                self.setInfo(VICAT_Info())
            else:
                Exception('Invalid Test Type.')
        except:
            raise Exception('Unknown Error Occured.')
        
    def setInfo(self, info):
        self.labels1 = info.labels1
        self.labels2 = info.labels2
        self.data1List = info.data1List
        self.data2List = info.data2List

class DSC_OIT_Info(InfoContainer):
    def __init__(self):
        self.labels1 = ["Deney No:",
                    "Numune Tarihi:",
                    "Test Baslama Tarihi:",
                    "Test Bitis Tarihi:",
                    "Ürün Kodu:",
                    "Numune Tanimi:",
                    "Numune Kodu:",
                    "Test Standardi:",
                    "Numune No:",
                    "Hammadde Kodu: ",
                    "Testi Yapan:"
                    ]
        
        self.labels2 = ["Test Süresi:",
                    "Azot Süresi:",
                    "OIT Süresi:",
                    "ΔH Erime Enerjisi:",
                    "Test Sicakligi:",
                    "Erime Sicakligi:",
                    "Referans Sicakligi:",
                    "Referans Agirligi:",
                    "Numune Agirlgii:",
                    "Note:",
                    "Testi Onaylayan:"
                    ]
        
        self.data1List = ["TestId", "UrunTarih", "TestBaslamaZamani", "TestBitisZamani", "UrunKodu",
                    "NumuneTanim", "NumuneKodu", "DeneyStandart", "NumuneNo", "HammaddeKodu",
                    "TestiYapanStr"]
        
        self.data2List = ["", "", "", "DeltaHAlan", "SetSicakligi",
                     "ErimeSicakligi", "NumuneKodu", "RefAgirlik", "NumuneAgirlik", "Aciklama",
                     "TestiOnaylayanStr"]
        
class MFI_Info(InfoContainer):
    def __init__(self):
        self.labels1 = ["Talep No:",
                    "Standart Adi:",
                    "Numune Bilgisi:",
                    "Sartlandirma:",
                    "On Isitma Suresi:",
                    "Diger Notlar:",
                    ]
        
        self.labels2 = ["Test Tarihi:",
                    "Deney Yuk(Kg):",
                    "Kalip Boyut:",
                    "Sicaklik(°C):",
                    "Kesme Zamani(sn):"
                    ]
        
        self.data1List = ["TalepNo", "StandartAdi", "NumuneBilgisi", 
                          "Sartlandirma", "IsitmaSure", "Diger"
                    ]
        
        self.data2List = ["TestTarih", "DeneyYuk", "KalipBoyu",
                          "DeneySicakligi", "KesimSuresi"
                     ]
        
class VICAT_Info(InfoContainer):
    def __init__(self):
        self.labels1 = ["Test No:",
                        "Test Baslama Tarihi:",
                        "Test Bitis Tarihi:",
                        "Ürün Tarihi:",
                        "Numune Tanimi:",
                        "Numune Kodu:",
                        "Hammadde Kodu:",
                        "Numune No:",
                        "Profil Kodu:",
                        "Deney Standardi:",
                        "Renk Kodu:",
                        "Notes:",
                        "Testi Yapan"
                    ]
        
        self.labels2 = ["Test Tipi:",
                        "Hat No:",
                        "Isitma Hizi:",
                        "Hammadde Gerilimi:",
                        "Numune Kalinlig:",
                        "Numune Genisligi:",
                        "Destekler Arasi Mesafe:",
                        "Referans Agirligi:",
                        "Agirlik:",
                        "Dikey Yuk:",
                        "Yatay Yuk:",
                        "Son Sicaklik",
                        "Testi Onaylayan"
                    ]
        
        self.data1List = ["test_id", "test_baslama_zamani", "test_bitis_zamani", "urun_tarih", "numune_tanimi",
                    "numune_kodu", "hammadde_kodu", "numune_no", " ", "deney_standardi", "", "aciklama"
                    "testi_yapan_str"]
        
        self.data2List = ["test_tipi", "hat_num", "isitma_hizi", "hammadde_gerilimi", "numune_kalinligi",
                     "numune_genisligi", "destekler_arasi_mesafe", "agirlik", "hesap_dikey_yuk", "hesap_yatay_yuk",
                     "son_sicaklik", "testi_onaylayan_str"]