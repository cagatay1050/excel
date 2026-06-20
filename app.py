import streamlit as st
import pandas as pd
import time
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

st.set_page_config(page_title="Ders Bilgi Güncelleyici", layout="centered", page_icon="📚")

st.title("📚 Ders Bilgi Paketi Otomatik Doldurucu")
st.markdown("""
Bu araç, yüklediğiniz Excel veya CSV dosyasındaki ders kodlarını okur, **Osmaniye Korkut Ata Üniversitesi Bologna Bilgi Sistemi'ne** bağlanır ve eksik olan *AKTS, Dersin Amacı, Haftalık Ders Saati* gibi bilgileri çekerek dosyanızı günceller.
""")

# Selenium WebDriver'ı Streamlit Cloud'a uygun şekilde hazırlayan fonksiyon
@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument('--headless') # Tarayıcıyı arka planda (arayüzsüz) çalıştırır
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Otomatik Chrome Driver kurulumu
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# Kullanıcıdan EXCEL veya CSV dosyasını alma
uploaded_file = st.file_uploader("Lütfen dosyanızı (.xlsx veya .csv) buraya yükleyin", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # YÖK formatındaki excelde asıl veriler 7. satırdan (index 6) başlar.
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=6)
        else:
            df = pd.read_excel(uploaded_file, skiprows=6)
            
        st.success("Dosya başarıyla okundu!")
        
        # Önizleme
        st.write("Dosya Önizlemesi (İlk 3 Satır):")
        st.dataframe(df.head(3))
        
        if st.button("🚀 Tarama İşlemini Başlat ve Güncelle"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Tarayıcıyı başlat
            status_text.info("Tarayıcı arka planda başlatılıyor... Lütfen bekleyin.")
            driver = get_driver()
            bologna_url = "https://obs.osmaniye.edu.tr/oibs/bologna/index.aspx?lang=tr&curOp=showPac&curUnit=29&curSunit=5815#"
            
            toplam_ders = len(df)
            
            # Veri Çekme Döngüsü
            for index, row in df.iterrows():
                ders_kodu = str(row['Dersin Kodu']).strip()
                
                # Ders kodu boşsa atla
                if pd.isna(row['Dersin Kodu']) or ders_kodu == "nan":
                    progress_bar.progress((index + 1) / toplam_ders)
                    continue
                    
                status_text.text(f"İşleniyor: {ders_kodu} aranıyor...")
                
                try:
                    # Ana sayfayı yeniden yükle
                    driver.get(bologna_url)
                    time.sleep(2)
                    
                    # 1. Tabloda ders kodunu bul ve linkine tıkla
                    xpath_sorgusu = f"//td[contains(text(), '{ders_kodu}')]/following-sibling::td/a"
                    ders_linki = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_sorgusu))
                    )
                    driver.execute_script("arguments[0].click();", ders_linki)
                    
                    # Sayfanın yüklenmesini bekle
                    time.sleep(2) 
                    
                    # 2. Detay sayfasından verileri çek
                    try:
                        akts = driver.find_element(By.XPATH, "//span[contains(@id, 'lblAKTS')]").text
                        df.at[index, 'AKTS'] = akts
                    except:
                        pass
                        
                    try:
                        ders_amaci = driver.find_element(By.XPATH, "//span[contains(@id, 'lblAmac')]").text
                        df.at[index, 'Dersin Amacı ve İçeriği'] = ders_amaci
                    except:
                        pass
                        
                    try:
                        haftalik_saat = driver.find_element(By.XPATH, "//span[contains(@id, 'lblTeorik')]").text
                        df.at[index, 'Haftalık Ders Saati'] = haftalik_saat
                    except:
                        pass
                    
                    # Bilgi paketi URL'sini kaydet
                    df.at[index, 'Varsa Ders Bilgi Paketi Adresi'] = driver.current_url
                    
                except Exception as e:
                    # Ders sitede bulunamazsa veya tıklanamazsa hata vermeden diğerine geç
                    pass
                
                # İlerleme çubuğunu güncelle
                progress_bar.progress((index + 1) / toplam_ders)

            status_text.success("Tüm dersler tarandı ve işlem tamamlandı! 🎉")
            
            # Güncellenmiş veriyi Excel (.xlsx) formatında belleğe kaydet (İndirme için)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Güncel Dersler')
            output.seek(0)
            
            # İndirme Butonu (Doğrudan Excel olarak)
            st.download_button(
                label="📥 Güncellenmiş Excel Dosyasını İndir",
                data=output,
                file_name='Doldurulmus_Dersler.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            
    except Exception as e:
        st.error(f"Dosya işlenirken bir hata oluştu. Hata Detayı: {e}")
