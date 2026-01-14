#!/usr/bin/env python3
"""
大車輪てつぼうくん (Daisharin Tetsubou-kun) Game
鉄棒ゲーム - タイミングよくボタンを押して360度回転を成功させよう！
"""

import pygame
import sys
import asyncio
from constants import *
from gymnast import Gymnast
from ui import UI

class Game:
    def __init__(self):
        # 最小限の初期化
        if not pygame.display.get_init():
            pygame.display.init()
        if not pygame.font.get_init():
            pygame.font.init()

        # ゲームウィンドウの設定
        self.WIDTH = SCREEN_WIDTH
        self.HEIGHT = SCREEN_HEIGHT
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("大車輪てつぼうくん - 飛距離チャレンジ")

        # 日本語入力（IME）を無効化
        try:
            pygame.key.stop_text_input()
        except AttributeError:
            pass # 古いバージョンや対応していない環境向け

        self.clock = pygame.time.Clock()
        self.FPS = FPS

        # ステージ設定
        self.BAR_Y = BAR_Y
        self.GROUND_Y = GROUND_Y

        # カメラ設定（初期値：鉄棒を中心に）
        self.camera_scale = 1.0
        self.camera_offset_x = 0
        self.camera_offset_y = self.HEIGHT / 2 - self.BAR_Y
        self.target_scale = 1.0
        self.target_offset_x = 0
        self.target_offset_y = self.HEIGHT / 2 - self.BAR_Y

        # 制限時間
        self.time_limit = TIME_LIMIT
        self.current_time = self.time_limit

        # 画像リソース
        self.img_cloud = None
        self.img_tree1 = None
        self.img_body_extended = None  # 体を伸ばした状態
        self.img_body_bent = None      # 体を曲げた状態
        try:
            self.img_cloud = pygame.image.load('image/clown.png').convert_alpha()
            self.img_tree1 = pygame.image.load('image/Tree1.png').convert_alpha()

            # 体の画像を読み込み、左右反転
            body1 = pygame.image.load('image/body1.png').convert_alpha()
            body2 = pygame.image.load('image/body2.png').convert_alpha()
            self.img_body_extended = pygame.transform.flip(body1, True, False)  # 左右反転
            self.img_body_bent = pygame.transform.flip(body2, True, False)      # 左右反転

        except Exception as e:
            print(f"Failed to load game assets: {e}")

        # 雲のワールド座標（Y座標を高く設定）
        self.clouds_world = [
            (-2000, -1800, 0.5),  # x, y, base_scale (相対的な雲の大きさ)
            (1000, -1200, 0.6),
            (3000, -2200, 0.4),
            (-500, -1500, 0.7),
            (2500, -1600, 0.55),
        ]

        # ゲームオブジェクトの初期化
        self.gymnast = Gymnast(self.WIDTH // 2, self.BAR_Y, self.img_body_extended, self.img_body_bent)
        self.ui = UI(self.WIDTH, self.HEIGHT)

        # パフォーマンス最適化：キャッシュ
        self._font_cache = {}
        self._scaled_cloud_cache = {}

        # ゲーム状態
        self.running = True
        self.is_started = False
        self.game_state = "waiting" # "waiting" -> "title" (after click)

    def handle_events(self):
        """イベント処理"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # 初回クリック/キーで開始
            if not self.is_started:
                if event.type in [pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN]:
                    # ここで初めて音声を初期化する
                    try:
                        pygame.mixer.init()
                        self.ui._load_sounds()
                    except Exception as e:
                        print(f"Mixer init failed: {e}")
                    
                    self.is_started = True
                    self.game_state = "title"
                    return

            if event.type == pygame.KEYDOWN:
                # タイトル画面でiキー: ヘルプ表示切り替え
                if self.game_state == "title" and event.key == pygame.K_i:
                    self.game_state = "help"
                elif self.game_state == "help" and (event.key == pygame.K_i or event.key == pygame.K_ESCAPE):
                    self.game_state = "title"

                # タイトル画面でEnterキー: ゲーム開始
                elif self.game_state == "title" and event.key == pygame.K_RETURN:
                    self.game_state = "playing"
                    self.current_time = self.time_limit # 時間リセット

                # スペースキー押下: 体の屈伸をトグル
                elif event.key == pygame.K_SPACE:
                    if self.game_state == "playing" and not self.gymnast.released:
                        self.gymnast.toggle_bend()

                # Enterキー: 鉄棒から離す
                elif event.key == pygame.K_RETURN:
                    if self.game_state == "playing" and not self.gymnast.released:
                        self.gymnast.release()
                        self.game_state = "flying" # 状態遷移

                # Rキー: リセット
                elif event.key == pygame.K_r:
                    self.reset_game()

    def update(self):
        """ゲームロジックの更新"""
        self.gymnast.update()

        # タイマー更新
        if self.game_state == "playing":
            self.current_time -= 1.0 / self.FPS
            if self.current_time <= 0:
                self.current_time = 0
                # 時間切れで強制リリース
                if not self.gymnast.released:
                    self.gymnast.release()
                    self.game_state = "flying"

        # カメラ更新
        if self.gymnast.released:
            # flying時：ダイナミックカメラ（選手を追従）
            
            # ターゲット座標（選手を画面中央に）
            target_gymnast_screen_x = self.WIDTH / 2
            target_gymnast_screen_y = self.HEIGHT / 2

            # ズーム率の計算（高度が高いほど、遠くへ行くほど引く）
            # 基準スケール
            base_scale = 1.0
            
            # 高度によるズームアウト
            height_diff = abs(self.gymnast.pos_y - self.GROUND_Y)
            # 地面に近いときは等倍近く、高いときは縮小
            # 高度2000pxでスケール0.3くらいになるように
            height_factor = max(0.0, (height_diff - 500) / 3000)
            
            # 距離によるズームアウト
            dist_diff = abs(self.gymnast.pos_x - self.WIDTH//2)
            dist_factor = max(0.0, (dist_diff - 500) / 4000)
            
            # ターゲットスケール決定
            self.target_scale = max(CAMERA_MIN_SCALE, 1.0 - (height_factor + dist_factor))
            
            # 地面付近での調整：地面が見えるように
            # 選手が地面に近い場合、スケールを少し戻して地面が見える範囲を確保してもいいが、
            # 上記の計算で自然に寄りになるはず。
            
            # オフセット計算：選手が画面中央に来るように
            # world_x * scale + offset_x = screen_x
            # offset_x = screen_x - world_x * scale
            self.target_offset_x = target_gymnast_screen_x - self.gymnast.pos_x * self.target_scale
            self.target_offset_y = target_gymnast_screen_y - self.gymnast.pos_y * self.target_scale
            
            # 地面より下を映しすぎないようにクランプ（地面が画面下部に来る位置を上限とする）
            # ground_screen_y = ground_y * scale + offset_y
            # ground_screen_y <= HEIGHT - margin
            # offset_y <= HEIGHT - margin - ground_y * scale
            max_offset_y = self.HEIGHT - 50 - self.GROUND_Y * self.target_scale
            self.target_offset_y = min(self.target_offset_y, max_offset_y)

        else:
            # 通常時は等倍、鉄棒を中心に（元の動作）
            self.target_scale = 1.0
            # 鉄棒を画面中央（横方向）に表示
            bar_x = self.WIDTH // 2
            self.target_offset_x = self.WIDTH / 2 - bar_x * self.target_scale
            # 鉄棒を画面中央（縦方向）に表示
            self.target_offset_y = self.HEIGHT / 2 - self.BAR_Y * self.target_scale

        # カメラのスムーズな移動
        self.camera_scale += (self.target_scale - self.camera_scale) * CAMERA_LERP_SPEED
        self.camera_offset_x += (self.target_offset_x - self.camera_offset_x) * CAMERA_LERP_SPEED
        self.camera_offset_y += (self.target_offset_y - self.camera_offset_y) * CAMERA_LERP_SPEED

        # 着地判定（強制成功）
        if self.game_state == "flying":
            # 判定を少し手前で行い、地面にめり込むのを防ぐ
            if self.gymnast.pos_y >= self.GROUND_Y - FOOT_OFFSET:
                self.game_state = "landed"
                self.gymnast.landed = True
                self.gymnast.pos_y = self.GROUND_Y - FOOT_OFFSET
                # 綺麗に着地させる（直立不動）
                self.gymnast.angle = 0
                self.gymnast.body_angle = 0
                self.gymnast.velocity_x = 0
                self.gymnast.velocity_y = 0
                
                distance = self.gymnast.pos_x - (self.WIDTH // 2)
                self.ui.set_result(distance)
        
        # UIアニメーション更新
        self.ui.update()

    def draw(self):
        """画面描画"""
        # 背景（柔らかい空色）
        self.screen.fill(SKY_COLOR)
        
        if self.game_state == "waiting":
            # 起動前の待機画面
            font = pygame.font.Font(None, 50)
            text = font.render("CLICK TO START", True, (60, 66, 82))
            rect = text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
            self.screen.blit(text, rect)
            pygame.display.flip()
            return

        # 雲を描く
        self.draw_clouds()

        # 変換パラメータ
        cam = {
            'ox': self.camera_offset_x,
            'oy': self.camera_offset_y,
            'scale': self.camera_scale
        }

        # 鉄棒装置
        self.draw_apparatus(cam)

        # 地面
        self.draw_ground(cam)

        # 選手
        self.gymnast.draw(self.screen, cam)

        # UI
        self.ui.draw(self.screen, self.gymnast.combo, self.current_time,
                     self.gymnast.is_bent,
                     self.gymnast.timing_quality, self.gymnast.timing_feedback_timer,
                     self.game_state)

        pygame.display.flip()
    
    def draw_clouds(self):
        """背景の雲（画像使用）"""
        if not self.img_cloud: return

        # 変換パラメータ（雲はカメラに追従）
        cam = {
            'ox': self.camera_offset_x,
            'oy': self.camera_offset_y,
            'scale': self.camera_scale
        }
        
        # 座標変換ヘルパー
        def to_screen(world_x, world_y):
            return (world_x * cam['scale'] + cam['ox'], world_y * cam['scale'] + cam['oy'])

        for cloud_world_x, cloud_world_y, base_scale in self.clouds_world:
            w, h = self.img_cloud.get_size()
            
            # カメラのスケールと雲のベーススケールを合わせて最終的なサイズを決定
            current_scale = base_scale * cam['scale']
            scaled_w = int(w * current_scale)
            scaled_h = int(h * current_scale)

            # サイズが小さすぎたら描画しない
            if scaled_w < 5 or scaled_h < 5: continue

            # キャッシュを使用して画像をスケーリング（パフォーマンス最適化）
            scaled_cloud = self._get_scaled_cloud(scaled_w, scaled_h)

            # ワールド座標をスクリーン座標に変換
            screen_x, screen_y = to_screen(cloud_world_x, cloud_world_y)

            # 雲の中心をワールド座標に合わせる
            cloud_rect = scaled_cloud.get_rect(center=(int(screen_x), int(screen_y)))

            self.screen.blit(scaled_cloud, cloud_rect)



    def draw_apparatus(self, cam):
        """鉄棒装置の描画"""
        self._draw_poles(cam)
        self._draw_bar(cam)

    def _to_screen(self, x, y, cam):
        """ワールド座標をスクリーン座標に変換"""
        return (x * cam['scale'] + cam['ox'], y * cam['scale'] + cam['oy'])

    def _draw_poles(self, cam):
        """支柱を描画（横から見た視点）"""
        bar_x = self.WIDTH // 2
        bar_y = self.BAR_Y

        # 横から見た視点：支柱は1本のみ表示
        pole_top = self._to_screen(bar_x, bar_y, cam)
        pole_bottom = self._to_screen(bar_x, self.GROUND_Y, cam)

        # 支柱の太さを半分にする (20 -> 10)
        pole_width = max(2, int(10 * cam['scale']))
        shadow_offset = max(1, int(3 * cam['scale']))
        highlight_offset = max(1, int(2 * cam['scale'])) # ハイライトも調整
        highlight_width = max(1, int(4 * cam['scale']))

        # 影
        pygame.draw.line(self.screen, POLE_COLOR_SHADOW,
                        (pole_top[0] - shadow_offset, pole_top[1]),
                        (pole_bottom[0] - shadow_offset, pole_bottom[1]), pole_width)

        # メイン
        pygame.draw.line(self.screen, POLE_COLOR_MAIN, pole_top, pole_bottom, pole_width)

        # ハイライト
        pygame.draw.line(self.screen, POLE_COLOR_HIGHLIGHT,
                        (pole_top[0] + highlight_offset, pole_top[1]),
                        (pole_bottom[0] + highlight_offset, pole_bottom[1]), highlight_width)

        # 支柱の上端（円形）
        pole_top_radius = max(2, int(5 * cam['scale'])) # 半径も半分 (10 -> 5)

        pygame.draw.circle(self.screen, POLE_COLOR_SHADOW,
                         (int(pole_top[0]), int(pole_top[1])), pole_top_radius)
        pygame.draw.circle(self.screen, POLE_COLOR_HIGHLIGHT,
                         (int(pole_top[0]), int(pole_top[1])), pole_top_radius - 1)

    def _draw_bar(self, cam):
        """バーを描画（横から見た視点：円形）"""
        bar_x = self.WIDTH // 2
        bar_y = self.BAR_Y

        # 横から見た鉄棒のバーは円形（断面）として表現
        bar_center = self._to_screen(bar_x, bar_y, cam)

        # バーの太さ（半径）を半分にする (15 -> 7.5)
        bar_radius = max(2, int(7.5 * cam['scale']))

        # 影（少し下にずらす）
        shadow_offset = max(1, int(1.5 * cam['scale']))
        pygame.draw.circle(self.screen, BAR_COLOR_SHADOW,
                         (int(bar_center[0]), int(bar_center[1] + shadow_offset)),
                         bar_radius)

        # メイン（鉄棒本体）
        pygame.draw.circle(self.screen, BAR_COLOR_MAIN,
                         (int(bar_center[0]), int(bar_center[1])),
                         bar_radius)

        # ハイライト（上部に光沢）
        highlight_radius = max(1, int(bar_radius * 0.6))
        highlight_offset_y = max(1, int(bar_radius * 0.3))
        pygame.draw.circle(self.screen, BAR_COLOR_HIGHLIGHT,
                         (int(bar_center[0]), int(bar_center[1] - highlight_offset_y)),
                         highlight_radius)

    def _get_cached_font(self, size):
        """フォントキャッシュから取得（パフォーマンス最適化）"""
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.Font(None, size)
        return self._font_cache[size]

    def _get_scaled_cloud(self, width, height):
        """スケール済み雲画像をキャッシュから取得（パフォーマンス最適化）"""
        key = (width, height)
        if key not in self._scaled_cloud_cache:
            self._scaled_cloud_cache[key] = pygame.transform.smoothscale(
                self.img_cloud, (width, height)
            )
        return self._scaled_cloud_cache[key]

    def draw_trees(self, cam, start_x, end_x, ground_y):
        """背景の木を描画（距離に応じて増える）"""
        if not self.img_tree1: return # img_tree2 もなくしたので条件変更

        import random

        # 木の基本サイズを統一（Tree1のサイズを基準にする）
        tree1_w, tree1_h = self.img_tree1.get_size()
        
        grid_size = 200
        start_grid = int(start_x / grid_size)
        end_grid = int(end_x / grid_size)

        for i in range(start_grid, end_grid + 1):
            random.seed(i)
            distance = abs(i * grid_size - self.WIDTH // 2)
            prob = 0.1 + min(0.7, distance / 15000.0)

            if random.random() < prob:
                offset_x = random.randint(0, grid_size - 1)
                world_x = i * grid_size + offset_x

                tree_img = self.img_tree1
                tree_w, tree_h = tree1_w, tree1_h

                scale_factor = 1.0

                screen_x = world_x * cam['scale'] + cam['ox']
                screen_y = ground_y * cam['scale'] + cam['oy']

                current_tree_w = tree_w * scale_factor * cam['scale']
                if screen_x + current_tree_w < 0 or screen_x > self.WIDTH:
                    continue

                scaled_w = int(tree_w * scale_factor * cam['scale'])
                scaled_h = int(tree_h * scale_factor * cam['scale'])

                if scaled_w < 2 or scaled_h < 2: continue

                scaled_tree = pygame.transform.smoothscale(tree_img, (scaled_w, scaled_h))

                tree_rect = scaled_tree.get_rect(midbottom=(screen_x, screen_y))
                self.screen.blit(scaled_tree, tree_rect)

    def draw_ground(self, cam):
        """地面の描画（優しい緑）"""
        ground_y = self.GROUND_Y

        # 画面左端から右端までのワールド座標を計算
        start_world_x = (0 - cam['ox']) / cam['scale']
        end_world_x = (self.WIDTH - cam['ox']) / cam['scale']

        # 画面上のY座標
        screen_ground_y = ground_y * cam['scale'] + cam['oy']

        # 木を描画（地面の奥）
        self.draw_trees(cam, start_world_x - 500, end_world_x + 500, ground_y)

        # 地面エリア塗りつぶし（画面外でも描画）
        if screen_ground_y < self.HEIGHT + 100:  # マージンを追加
            ground_height = max(self.HEIGHT - int(screen_ground_y), 0) + 100
            pygame.draw.rect(self.screen, GROUND_COLOR,
                           (0, max(0, int(screen_ground_y)), self.WIDTH, ground_height))
            
        # 距離マーカー（100mごと）
        center_x = self.WIDTH // 2

        # マーカー描画範囲を広げる
        marker_start = int(start_world_x / DISTANCE_MARKER_INTERVAL) * DISTANCE_MARKER_INTERVAL
        marker_end = int(end_world_x / DISTANCE_MARKER_INTERVAL) * DISTANCE_MARKER_INTERVAL + 2000

        # フォントサイズ（スケーリング考慮、キャッシュ使用）
        base_font_size = 120
        current_font_size = max(20, int(base_font_size * cam['scale']))
        font = self._get_cached_font(current_font_size)

        for mx in range(marker_start, marker_end, DISTANCE_MARKER_INTERVAL):
            sx = mx * cam['scale'] + cam['ox']
            sy = screen_ground_y

            # 画面外も少し含めて描画
            if -100 <= sx <= self.WIDTH + 100:
                # 距離テキスト (ピクセル -> メートル換算)
                dist = int((mx - center_x) / DISTANCE_SCALE)

                # 100m単位は極太ラインとテキスト
                line_length = max(40, int(60 * cam['scale'] / 0.15))
                line_width = max(4, int(6 / cam['scale'] * 0.15))
                
                # 白いライン
                pygame.draw.line(self.screen, (255, 255, 255),
                               (sx, sy), (sx, sy + line_length), line_width)
                
                if dist != 0 and cam['scale'] > 0.05:
                    text = f"{abs(dist)}m"
                    text_surf = font.render(text, True, (255, 255, 255))
                    # テキストの位置調整（ラインの下）
                    text_rect = text_surf.get_rect(center=(sx, sy + line_length + current_font_size))
                    self.screen.blit(text_surf, text_rect)


    def reset_game(self):
        """ゲームのリセット"""
        self.gymnast = Gymnast(self.WIDTH // 2, self.BAR_Y, self.img_body_extended, self.img_body_bent)
        self.game_state = "title"
        self.camera_scale = 1.0
        self.camera_offset_x = 0
        self.camera_offset_y = self.HEIGHT / 2 - self.BAR_Y
        self.ui.reset_result()
        self.current_time = self.time_limit # 時間もリセット
        
        # IME無効化を再適用（念のため）
        try:
            pygame.key.stop_text_input()
        except AttributeError:
            pass

    async def run(self):
        """メインゲームループ"""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(self.FPS)
            await asyncio.sleep(0)

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Game()
    asyncio.run(game.run())