"""
UIクラス - モダンUI、アニメーション、パーティクル演出
"""

import pygame
import math
import random
import os
from constants import *

class Particle:
    """パーティクル（紙吹雪などの粒子）クラス"""
    def __init__(self, x, y, color, size, speed, angle, lifetime):
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.gravity = 0.2
        self.friction = 0.95
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.angle = random.random() * 360
        self.rotation_speed = random.uniform(-5, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.vx *= self.friction
        self.vy *= self.friction
        self.angle += self.rotation_speed
        self.lifetime -= 1
        return self.lifetime > 0

    def draw(self, surface):
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        if alpha <= 0: return
        
        # 回転する正方形を描画
        s = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.rect(s, (*self.color, alpha), (0, 0, self.size, self.size))
        s = pygame.transform.rotate(s, self.angle)
        rect = s.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(s, rect)

class UI:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # フォント設定
        self.font_title = self._load_safe_font(50)
        self.font_score = self._load_safe_font(60)
        self.font_large = self._load_safe_font(40)
        self.font_medium = self._load_safe_font(28)
        self.font_small = self._load_safe_font(20)
        self.font_tiny = self._load_safe_font(16)
        self.font_bold = self._load_safe_font(24)

        # モダンカラーパレット
        self.colors = {
            'WHITE': (255, 255, 255),
            'TEXT_MAIN': (60, 66, 82),      # ダークグレー
            'TEXT_SUB': (130, 136, 150),    # ライトグレー
            'ACCENT_CYAN': (45, 200, 220),  # シアン
            'ACCENT_PINK': (255, 100, 150), # ピンク
            'ACCENT_ORANGE': (255, 180, 60),# オレンジ
            'ACCENT_GREEN': (100, 220, 140),# グリーン
            'PANEL_BG': (255, 255, 255, 220), # 半透明白
            'SHADOW': (0, 0, 0, 40),
            'KEY_BG': (245, 247, 250),
            'KEY_BORDER': (210, 215, 225)
        }

        # アニメーション管理
        self.particles = []
        self.anim_timer = 0
        self.combo_scale = 1.0
        self.result_panel_y = screen_height # 下から出てくるアニメーション用
        self.target_result_panel_y = (screen_height - 400) // 2
        
        # リザルト数値カウントアップ用
        self.display_distance = 0.0
        self.final_distance = 0.0
        self.is_result_shown = False

        # 直前の状態
        self.last_combo = 0

        # 音源
        self.sounds = {}
        self._load_sounds()

    def _load_sounds(self):
        """音源の読み込み（エラー回避付き）"""
        if not pygame.mixer.get_init():
            return

        sound_files = {
            'button': 'sounds/button.wav',
            'swing': 'sounds/swing.wav',
            'land_ok': 'sounds/land_ok.wav'
        }
        for name, path in sound_files.items():
            try:
                if os.path.exists(path):
                    self.sounds[name] = pygame.mixer.Sound(path)
            except Exception as e:
                print(f"Could not load sound {name}: {e}")

    def play_button_sound(self):
        if 'button' in self.sounds:
            self.sounds['button'].play()

    def play_swing_sound(self):
        if 'swing' in self.sounds:
            self.sounds['swing'].play()

    def play_landing_sound(self, success=True):
        if 'land_ok' in self.sounds:
            self.sounds['land_ok'].play()

    def _load_safe_font(self, size):
        """フォント読み込み（プロジェクト内フォント優先）"""
        # プロジェクト内のフォントを最優先（Web/ローカル両対応）
        try:
            return pygame.font.Font("font/mplus-rounded.ttf", size)
        except Exception:
            pass

        # macOS用フォールバック
        macos_font_paths = [
            "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"
        ]
        for path in macos_font_paths:
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
        return pygame.font.Font(None, size)

    def update(self):
        """毎フレームの更新処理（アニメーション・パーティクル）"""
        self.anim_timer += 1
        
        # パーティクル更新
        self.particles = [p for p in self.particles if p.update()]
        
        # コンボアニメーションの減衰
        if self.combo_scale > 1.0:
            self.combo_scale += (1.0 - self.combo_scale) * 0.1

        # リザルトパネルのアニメーション
        if self.is_result_shown:
            # パネルのスライドイン
            self.result_panel_y += (self.target_result_panel_y - self.result_panel_y) * 0.1
            
            # 数値のカウントアップ
            if abs(self.display_distance - self.final_distance) > 0.1:
                self.display_distance += (self.final_distance - self.display_distance) * 0.1
            else:
                self.display_distance = self.final_distance

    def create_confetti(self, x, y, count=20):
        """紙吹雪を発生させる"""
        colors = [
            self.colors['ACCENT_CYAN'], self.colors['ACCENT_PINK'],
            self.colors['ACCENT_ORANGE'], self.colors['ACCENT_GREEN']
        ]
        for _ in range(count):
            color = random.choice(colors)
            size = random.randint(4, 8)
            speed = random.uniform(2, 8)
            angle = random.uniform(0, math.pi * 2) # 全方向
            lifetime = random.randint(30, 60)
            self.particles.append(Particle(x, y, color, size, speed, angle, lifetime))

    def create_sparkle(self, x, y):
        """コンボ用のきらめき"""
        self.create_confetti(x, y, count=5)

    def draw_rounded_rect(self, surface, color, rect, radius=15, width=0):
        """角丸長方形描画（高品質）"""
        rect = pygame.Rect(rect)
        color = pygame.Color(*color)
        alpha = color.a
        color.a = 0
        pos = rect.topleft
        rect.topleft = 0,0
        rectangle = pygame.Surface(rect.size, pygame.SRCALPHA)

        circle = pygame.Surface([min(rect.size)*3]*2, pygame.SRCALPHA)
        pygame.draw.ellipse(circle, (0,0,0), circle.get_rect(), 0)
        circle = pygame.transform.smoothscale(circle, [int(min(rect.size)*0.5)]*2)

        radius = width if radius < width else radius

        if radius > 0:
            circle_tl = pygame.transform.smoothscale(circle, (radius*2, radius*2))
            if width == 0:
                rectangle.blit(circle_tl, (0, 0))
                rectangle.blit(circle_tl, (rect.width - radius*2, 0))
                rectangle.blit(circle_tl, (0, rect.height - radius*2))
                rectangle.blit(circle_tl, (rect.width - radius*2, rect.height - radius*2))
                rectangle.fill((0, 0, 0), (radius, 0, rect.width - radius*2, rect.height))
                rectangle.fill((0, 0, 0), (0, radius, rect.width, rect.height - radius*2))
            else:
                # 枠線は簡易実装
                pygame.draw.rect(rectangle, (0,0,0), rect, width, border_radius=radius)
        else:
            pygame.draw.rect(rectangle, (0,0,0), rect, width)

        rectangle.fill(color, special_flags=pygame.BLEND_RGBA_MAX)
        rectangle.fill((color.r, color.g, color.b, alpha), special_flags=pygame.BLEND_RGBA_MIN)
        surface.blit(rectangle, pos)

    def draw_panel(self, screen, x, y, width, height):
        """影付きパネル"""
        rect = pygame.Rect(x, y, width, height)
        # 影
        self.draw_rounded_rect(screen, self.colors['SHADOW'], rect.move(0, 8), radius=20)
        # 本体
        self.draw_rounded_rect(screen, self.colors['PANEL_BG'], rect, radius=20)

    def draw_key(self, screen, text, x, y, pressed=False):
        """キーアイコン"""
        w, h = 60, 50
        offset = 4 if not pressed else 2
        bg_color = self.colors['KEY_BORDER']
        key_color = self.colors['KEY_BG'] if not pressed else (230, 230, 235)
        
        # 土台
        self.draw_rounded_rect(screen, bg_color, (x, y + offset, w, h), radius=10)
        # キー
        self.draw_rounded_rect(screen, key_color, (x, y, w, h), radius=10)
        
        # 文字
        txt = self.font_bold.render(text, True, self.colors['TEXT_MAIN'])
        screen.blit(txt, txt.get_rect(center=(x + w//2, y + h//2)))

    def draw(self, screen, combo, time_left, is_bent, timing_quality, timing_timer, game_state):
        """描画メイン"""
        
        # パーティクル描画（背景より手前、UIより奥）
        for p in self.particles:
            p.draw(screen)

        if game_state == "title":
            self._draw_title(screen)
        elif game_state == "help":
            self._draw_help(screen)
        elif game_state in ["playing", "flying"]:
            self._draw_hud(screen, combo, time_left, is_bent, timing_quality, timing_timer)
        
        if game_state == "landed":
             self._draw_result(screen)

        # コンボ変化検知でエフェクト
        if combo > self.last_combo:
            self.combo_scale = 1.5 # 弾む
            self.create_sparkle(self.screen_width - 150, 100) # キラキラ
        self.last_combo = combo

    def _draw_title(self, screen):
        """タイトル画面"""
        # ロゴのアニメーション（ふわふわ）
        offset_y = 0

        center_x = self.screen_width // 2
        center_y = self.screen_height // 2 - 50 + offset_y

        # タイトルロゴ（テキスト）
        text = "大車輪てつぼうくん"
        # 影
        shadow = self.font_title.render(text, True, (255,255,255))
        screen.blit(shadow, shadow.get_rect(center=(center_x+4, center_y+4)))
        # 本体
        main = self.font_title.render(text, True, self.colors['ACCENT_CYAN'])
        screen.blit(main, main.get_rect(center=(center_x, center_y)))

        # Press Enter（ブレスアニメーション）
        alpha = int(155 + math.sin(self.anim_timer * 0.1) * 100)
        press_text = self.font_bold.render("PRESS ENTER TO START", True, self.colors['ACCENT_PINK'])
        press_text.set_alpha(alpha)
        screen.blit(press_text, press_text.get_rect(center=(center_x, self.screen_height - 100)))

        # 操作ガイド
        self.draw_key(screen, "SPC", center_x - 120, self.screen_height - 180)
        screen.blit(self.font_small.render("加速", True, self.colors['TEXT_MAIN']), (center_x - 50, self.screen_height - 165))

        self.draw_key(screen, "ENT", center_x + 20, self.screen_height - 180)
        screen.blit(self.font_small.render("ジャンプ", True, self.colors['TEXT_MAIN']), (center_x + 90, self.screen_height - 165))

    def _draw_help(self, screen):
        """ヘルプ画面（詳細な遊び方）"""
        panel_w, panel_h = 700, 500
        px = (self.screen_width - panel_w) // 2
        py = (self.screen_height - panel_h) // 2
        
        self.draw_panel(screen, px, py, panel_w, panel_h)
        
        center_x = self.screen_width // 2
        
        # タイトル
        title = self.font_large.render("あそびかた", True, self.colors['ACCENT_CYAN'])
        screen.blit(title, title.get_rect(center=(center_x, py + 40)))
        
        # 説明文
        lines = [
            "1. 加速する",
            "   タイミングよく SPACE キーを押して回転を加速させよう！",
            "   - 上昇するときに「縮む（押す）」",
            "   - 下降するときに「伸ばす（離す）」",
            "   連続で成功するとコンボボーナスでさらに加速！",
            "",
            "2. ジャンプ！",
            "   十分に加速したら ENTER キーで手を離してジャンプ！",
            "   斜め上（45度くらい）に飛び出すのが飛距離を伸ばすコツ。",
            "   制限時間30秒以内に飛ばないと強制的に離しちゃうぞ。",
            "",
            "3. 着地",
            "   着地は自動判定。どれだけ遠くへ飛べるか挑戦しよう！"
        ]
        
        y = py + 85
        for i, line in enumerate(lines):
            if i in [0, 6, 11]: # 見出し
                color = self.colors['ACCENT_ORANGE']
                font = self.font_small
                offset = 8
            else:
                color = self.colors['TEXT_MAIN']
                font = self.font_tiny
                offset = 0
                
            text_surf = font.render(line, True, color)
            screen.blit(text_surf, (px + 60, y))
            y += 24 + offset

        # 戻る案内
        back_text = self.font_bold.render("PRESS ESC or I TO RETURN", True, self.colors['TEXT_SUB'])
        screen.blit(back_text, back_text.get_rect(center=(center_x, py + panel_h - 40)))

    def _draw_hud(self, screen, combo, time_left, is_bent, quality, timer):
        """プレイ中HUD"""
        
        # タイマー（上部中央）
        t_color = self.colors['TEXT_MAIN']
        if time_left < 10: t_color = self.colors['ACCENT_PINK'] # 警告色
        
        panel_w, panel_h = 160, 70
        px = (self.screen_width - panel_w) // 2
        py = 30
        self.draw_panel(screen, px, py, panel_w, panel_h)
        
        t_str = f"{max(0, time_left):.1f}"
        t_surf = self.font_medium.render(t_str, True, t_color)
        screen.blit(t_surf, t_surf.get_rect(center=(px + panel_w//2, py + panel_h//2 + 5)))
        
        lbl = self.font_small.render("TIME", True, self.colors['TEXT_SUB'])
        screen.blit(lbl, (px + 15, py + 8))
        
        # コンボ表示（右上の弾む数字）
        if combo > 1:
            cx, cy = self.screen_width - 100, 80
            scale = self.combo_scale
            
            # コンボ数に応じた色
            c_color = self.colors['ACCENT_CYAN']
            if combo >= 10: c_color = self.colors['ACCENT_ORANGE']
            if combo >= 20: c_color = self.colors['ACCENT_PINK']
            
            # スケーリングしたフォント描画（簡易的に画像スケーリング）
            c_str = str(combo)
            base_surf = self.font_score.render(c_str, True, c_color)
            w, h = base_surf.get_size()
            scaled_surf = pygame.transform.smoothscale(base_surf, (int(w*scale), int(h*scale)))
            
            screen.blit(scaled_surf, scaled_surf.get_rect(center=(cx, cy)))
            
            lbl_surf = self.font_bold.render("COMBO", True, self.colors['TEXT_SUB'])
            screen.blit(lbl_surf, lbl_surf.get_rect(center=(cx, cy + 40)))

        # 判定表示
        if timer > 0:
            q_text = ""
            q_color = self.colors['TEXT_MAIN']
            if quality == "perfect":
                q_text = "PERFECT!!"
                q_color = self.colors['ACCENT_ORANGE']
            elif quality == "good":
                q_text = "GOOD!"
                q_color = self.colors['ACCENT_GREEN']
            elif quality == "poor":
                q_text = "MISS..."
                q_color = self.colors['TEXT_SUB']
            
            if q_text:
                # フェード＆上昇アニメーション
                alpha = min(255, timer * 15)
                dy = (40 - timer) * 2
                
                surf = self.font_large.render(q_text, True, q_color)
                surf.set_alpha(alpha)
                screen.blit(surf, surf.get_rect(center=(self.screen_width//2, 200 - dy)))

        # 操作インジケータ（左下）
        ix, iy = 40, self.screen_height - 100
        self.draw_key(screen, "SPC", ix, iy, pressed=is_bent)
        action_text = "縮む" if is_bent else "伸ばす"
        screen.blit(self.font_small.render(action_text, True, self.colors['TEXT_MAIN']), (ix + 70, iy + 15))

        # Enterで離すガイド（その右）
        ex = ix + 160
        self.draw_key(screen, "ENT", ex, iy)
        screen.blit(self.font_small.render("離す", True, self.colors['TEXT_MAIN']), (ex + 70, iy + 15))

    def _draw_result(self, screen):
        """リザルト画面（下からスライドイン）"""
        panel_w, panel_h = 500, 400
        px = (self.screen_width - panel_w) // 2
        py = self.result_panel_y # アニメーション座標
        
        self.draw_panel(screen, px, py, panel_w, panel_h)
        
        center_x = px + panel_w // 2
        
        # タイトル
        screen.blit(self.font_large.render("RESULT", True, self.colors['ACCENT_CYAN']), (px + 40, py + 40))
        
        # スコア（ドラムロール風）
        dist_str = f"{self.display_distance:.2f} m"
        score_surf = self.font_score.render(dist_str, True, self.colors['TEXT_MAIN'])
        screen.blit(score_surf, score_surf.get_rect(center=(center_x, py + 150)))
        
        # ランク表示（ドラムロール完了後に表示）
        if abs(self.display_distance - self.final_distance) < 0.1:
            rank = "D"
            color = self.colors['TEXT_SUB']
            ad = abs(self.final_distance)
            if ad >= 1000: rank, color = "SSS", self.colors['ACCENT_ORANGE']
            elif ad >= 800: rank, color = "SS", self.colors['ACCENT_ORANGE']
            elif ad >= 600: rank, color = "S", self.colors['ACCENT_PINK']
            elif ad >= 400: rank, color = "A", self.colors['ACCENT_PINK']
            elif ad >= 200: rank, color = "B", self.colors['ACCENT_CYAN']
            elif ad >= 100: rank, color = "C", self.colors['ACCENT_GREEN']

            r_surf = self.font_large.render(f"Rank {rank}", True, color)
            screen.blit(r_surf, r_surf.get_rect(center=(center_x, py + 230)))
            
            # リトライ案内
            self.draw_key(screen, "R", center_x - 30, py + 300)
            screen.blit(self.font_small.render("RETRY", True, self.colors['TEXT_MAIN']), (center_x + 40, py + 315))

    # 外部からのデータセット用メソッド
    def set_result(self, distance):
        self.final_distance = distance / 10.0
        self.display_distance = 0.0 # カウントアップ開始値
        self.is_result_shown = True
        self.result_panel_y = self.screen_height # 初期位置リセット
        # パーティクル発生
        if abs(self.final_distance) >= 100:
            self.create_confetti(self.screen_width//2, self.screen_height//2, count=50)

    def reset_result(self):
        self.is_result_shown = False
        self.final_distance = 0.0
        self.display_distance = 0.0
        self.particles = [] # パーティクルリセット