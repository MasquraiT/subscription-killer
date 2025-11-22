import os
import json
from datetime import datetime, timedelta
import threading
import time

from kivy.lang import Builder
from kivy.core.window import Window
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineAvatarIconListItem, IconLeftWidget, IRightBodyTouch
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.pickers import MDDatePicker
from kivymd.uix.textfield import MDTextField
from kivymd.uix.menu import MDDropdownMenu
from kivymd.toast import toast
from plyer import notification
from kivy.utils import platform

# Pencere Boyutu (Sadece PC'de test ederken telefon gibi görünsün diye)
if platform != 'android':
    Window.size = (400, 750)

# --- UYGULAMA ARAYÜZÜ (KV Dili) ---
KV = '''
<SubscriptionItem>:
    on_release: app.delete_dialog(self)
    IconLeftWidget:
        icon: root.icon_name
        theme_text_color: "Custom"
        text_color: 1, 0.2, 0.2, 1  # Kırmızı ikon

    DeleteButton:
        icon: "trash-can-outline"
        on_release: app.delete_dialog(root)

MDScreen:
    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            title: "Subscription Killer"
            elevation: 2
            pos_hint: {"top": 1}
            md_bg_color: 0.1, 0.1, 0.1, 1
            specific_text_color: 1, 0.2, 0.2, 1
            right_action_items: [["bell-ring", lambda x: app.test_notification()]]

        MDScrollView:
            MDList:
                id: sub_list
                padding: "10dp"
                spacing: "10dp"

    MDFloatingActionButton:
        icon: "plus"
        md_bg_color: 1, 0.2, 0.2, 1
        pos_hint: {"right": 0.95, "bottom": 0.05}
        on_release: app.show_add_dialog()
'''

# --- YARDIMCI SINIFLAR ---
class DeleteButton(IRightBodyTouch, MDIconButton):
    pass

class SubscriptionItem(TwoLineAvatarIconListItem):
    icon_name = "application"  # Varsayılan ikon
    sub_id = "" # Silme işlemi için kimlik

# --- ANA UYGULAMA SINIFI ---
class SubscriptionKillerApp(MDApp):
    def build(self):
        # TEMA AYARLARI
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Red"
        self.theme_cls.material_style = "M3"
        
        # Veritabanı Dosyası
        self.data_file = 'subscriptions.json'
        self.active_subscriptions = []
        
        # Platform İkonları Eşleştirmesi
        self.platform_icons = {
            "Netflix": "netflix",
            "Spotify": "spotify",
            "YouTube Premium": "youtube",
            "Amazon Prime": "amazon",
            "Disney+": "video-vintage",
            "Exxen": "soccer",
            "BluTV": "television-classic",
            "Gain": "play-circle",
            "Apple Music": "apple",
            "iCloud": "cloud",
            "Google One": "google-drive",
            "Tinder": "fire",
            "Adobe": "pencil-ruler",
            "Diğer": "credit-card-clock"
        }

        return Builder.load_string(KV)

    def on_start(self):
        """Uygulama açıldığında verileri yükle"""
        self.load_data()
        self.refresh_list()
        # Arka plan kontrolünü başlat
        threading.Thread(target=self.background_check, daemon=True).start()

    # --- VERİ YÖNETİMİ ---
    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.active_subscriptions = json.load(f)
            except:
                self.active_subscriptions = []

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.active_subscriptions, f)

    # --- ARAYÜZ GÜNCELLEME ---
    def refresh_list(self):
        self.root.ids.sub_list.clear_widgets()
        
        if not self.active_subscriptions:
            return

        for sub in self.active_subscriptions:
            # Kalan gün hesapla
            end_date = datetime.strptime(sub['end_date'], "%Y-%m-%d")
            days_left = (end_date - datetime.now()).days + 1
            
            icon = self.platform_icons.get(sub['name'], "credit-card-clock")
            
            item = SubscriptionItem(
                text=f"{sub['name']}",
                secondary_text=f"İptal için son: {days_left} Gün kaldı! ({sub['end_date']})",
                icon_name=icon
            )
            item.sub_id = sub['id']
            self.root.ids.sub_list.add_widget(item)

    # --- EKLEME DİYALOĞU ---
    def show_add_dialog(self):
        # İçerik düzeni
        content = MDBoxLayout(orientation="vertical", spacing="12dp", size_hint_y=None, height="200dp")
        
        # Platform Seçimi (Menu için buton)
        self.platform_btn = MDRaisedButton(
            text="Platform Seç", 
            pos_hint={"center_x": .5},
            md_bg_color=(0.2, 0.2, 0.2, 1)
        )
        self.platform_btn.bind(on_release=self.open_menu)
        
        # Tarih Seçimi
        self.date_btn = MDRaisedButton(
            text="Bitiş Tarihini Seç", 
            pos_hint={"center_x": .5},
            md_bg_color=(0.8, 0, 0, 1)
        )
        self.date_btn.bind(on_release=self.show_date_picker)

        self.selected_platform = None
        self.selected_date = None

        content.add_widget(self.platform_btn)
        content.add_widget(self.date_btn)

        self.dialog = MDDialog(
            title="Yeni Abonelik Ekle",
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="İPTAL", text_color=(1,1,1,1), on_release=self.close_dialog),
                MDRaisedButton(text="KAYDET", md_bg_color=(1,0,0,1), on_release=self.save_subscription),
            ],
        )
        self.dialog.open()

    # --- MENÜ VE TARİH SEÇİCİ ---
    def open_menu(self, instance):
        menu_items = [
            {
                "text": name,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=name: self.set_platform(x),
            } for name in self.platform_icons.keys()
        ]
        self.menu = MDDropdownMenu(
            caller=instance,
            items=menu_items,
            width_mult=4,
        )
        self.menu.open()

    def set_platform(self, text):
        self.selected_platform = text
        self.platform_btn.text = text
        self.menu.dismiss()

    def show_date_picker(self, instance):
        date_dialog = MDDatePicker()
        date_dialog.bind(on_save=self.on_date_save)
        date_dialog.open()

    def on_date_save(self, instance, value, date_range):
        self.selected_date = value.strftime("%Y-%m-%d")
        self.date_btn.text = f"Bitiş: {self.selected_date}"

    def close_dialog(self, *args):
        self.dialog.dismiss()

    def save_subscription(self, *args):
        if not self.selected_platform or not self.selected_date:
            toast("Lütfen Platform ve Tarih seçin!")
            return
        
        new_sub = {
            "id": str(int(time.time())), # Benzersiz ID
            "name": self.selected_platform,
            "end_date": self.selected_date
        }
        
        self.active_subscriptions.append(new_sub)
        self.save_data()
        self.refresh_list()
        self.close_dialog()
        toast("Takip Başlatıldı!")

    # --- SİLME İŞLEMİ ---
    def delete_dialog(self, item):
        self.item_to_delete = item
        self.del_dialog = MDDialog(
            title="Silinsin mi?",
            text=f"{item.text} takibi kaldırılsın mı?",
            buttons=[
                MDRaisedButton(text="HAYIR", on_release=lambda x: self.del_dialog.dismiss()),
                MDRaisedButton(text="EVET, SİL", md_bg_color=(1,0,0,1), on_release=self.delete_subscription)
            ]
        )
        self.del_dialog.open()

    def delete_subscription(self, *args):
        sub_id = self.item_to_delete.sub_id
        self.active_subscriptions = [s for s in self.active_subscriptions if s['id'] != sub_id]
        self.save_data()
        self.refresh_list()
        self.del_dialog.dismiss()

    # --- BİLDİRİM SİSTEMİ ---
    def test_notification(self):
        """Test amaçlı manuel bildirim"""
        self.send_notification("Test", "Bildirimler sorunsuz çalışıyor!")

    def send_notification(self, title, message):
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Subscription Killer",
                app_icon=None,
                timeout=10,
            )
        except Exception as e:
            print(f"Bildirim hatası: {e}")

    def background_check(self):
        """Arka planda saat başı kontrol yap"""
        while True:
            now = datetime.now()
            for sub in self.active_subscriptions:
                end_date = datetime.strptime(sub['end_date'], "%Y-%m-%d")
                
                # Kalan süre hesapla
                diff = end_date - now
                days = diff.days
                
                # Kritik eşikler: 3 gün kala, 1 gün kala ve bugün
                if days in [3, 1, 0]:
                    # O gün daha önce bildirim atılmamışsa (basit mantık)
                    # Gerçek bir uygulamada 'last_notified' tarihi tutulur.
                    # Şimdilik saat başı uyarı modunu aktif tutuyoruz.
                     self.send_notification(
                        "DİKKAT! PARA KESİLECEK!",
                        f"{sub['name']} deneme süresi bitmek üzere! ({days} gün kaldı)"
                    )
            
            # 1 Saat bekle (3600 saniye)
            time.sleep(3600)

if __name__ == "__main__":
    SubscriptionKillerApp().run()
    
