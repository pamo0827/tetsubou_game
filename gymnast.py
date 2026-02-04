"""
選手クラス - 物理演算とアニメーション
改良版：慣性モーメント変化と角運動量保存を実装
"""

import pygame
import math
from constants import *

class Gymnast:
    def __init__(self, bar_x, bar_y, img_body_extended=None, img_body_bent=None):
        """
        選手の初期化

        Args:
            bar_x: 鉄棒のX座標
            bar_y: 鉄棒のY座標
            img_body_extended: 体を伸ばした状態の画像
            img_body_bent: 体を曲げた状態の画像
        """
        # 鉄棒の位置
        self.bar_x = bar_x
        self.bar_y = bar_y

        # 体の画像
        self.img_body_extended = img_body_extended
        self.img_body_bent = img_body_bent

        # 物理パラメータ（現実世界の物理を再現）
        self.angle = 0.0  # 初期角度（真下）
        self.angular_velocity = 0.05  # 初期速度を少し付与
        self.angular_momentum = 0.0  # 角運動量（保存される）
        self.gravity = GRAVITY_SWING  # 重力（よりリアルに調整）
        self.damping = DAMPING  # 減衰係数（飛距離を伸ばすため、減衰を少し緩和）

        # 選手のパラメータ
        self.arm_length = ARM_LENGTH  # 鉄棒から重心までの距離
        self.mass = 1.0  # 質量（相対値）
        self.released = False  # 離したかどうか
        self.rotation_count = 0  # 回転数
        self.last_angle = self.angle

        # 屈伸状態（重要！）
        self.is_bent = False  # 体を折り曲げているか
        self.bent_ratio = BENT_RATIO_EXTENDED  # 屈伸率（1.0=伸びた, 0.65=曲がった）
        self.target_bent_ratio = BENT_RATIO_EXTENDED

        # 慣性モーメント（体の伸縮によって変化）
        self.moment_of_inertia_extended = self.mass * (self.arm_length ** 2)  # 伸びた状態
        self.moment_of_inertia_bent = self.moment_of_inertia_extended * 0.5  # 曲がった状態（50%）

        # 着地状態
        self.landed = False
        self.velocity_x = 0  # 水平速度
        self.velocity_y = 0  # 垂直速度
        self.pos_x = 0
        self.pos_y = 0

        # アニメーション
        self.body_angle = 0  # 体の角度（回転表現用）
        self.trail = [] # 軌跡用リスト [(x, y), ...]

        # エネルギー追加のタイミング判定
        self.last_velocity_sign = 0
        self.timing_quality = "good"  # perfect, good, poor
        self.timing_feedback_timer = 0  # タイミングフィードバック表示用
        self.combo = 0 # 連続Perfectコンボ数

    def bend(self):
        """
        体を折り曲げる（黄色ボタン押下＝スペースキー押す）
        瞬時に下半身を90度折り曲げる
        """
        if not self.released and not self.is_bent:
            self.is_bent = True
            self.target_bent_ratio = BENT_RATIO_BENT  # 折り曲げ状態
            # タイミングによるエネルギー追加判定
            self.check_timing_bonus()

    def extend(self):
        """
        体を伸ばす（黄色ボタン離す＝スペースキー離す）
        """
        if not self.released and self.is_bent:
            self.is_bent = False
            self.target_bent_ratio = BENT_RATIO_EXTENDED  # 伸びた状態
            # タイミングによるエネルギー追加判定
            self.check_timing_bonus()

    def toggle_bend(self):
        """
        体の屈伸をトグル（スペースキーを押すたびに曲げる↔伸ばすを切り替え）
        """
        if not self.released:
            if self.is_bent:
                # 現在曲げている → 伸ばす
                self.extend()
            else:
                # 現在伸びている → 曲げる
                self.bend()

    def _calculate_max_angle(self):
        """
        現在のエネルギーから最大到達角度（振幅）を推定する
        """
        # 現在の運動エネルギー + ポテンシャルエネルギー
        # E = 1/2 I w^2 + m g r (1 - cos(theta))
        # 基準: 最下点(0)
        
        # 現在のパラメータ
        current_r = self.arm_length * self.bent_ratio
        current_I = self.mass * (current_r ** 2)
        
        # 運動エネルギー
        ke = 0.5 * current_I * (self.angular_velocity ** 2)
        
        # ポテンシャルエネルギー (最下点基準)
        # cos(0)=1 -> 1-1=0.
        # cos(pi)=-1 -> 1-(-1)=2.
        pe = self.mass * self.gravity * current_r * (1.0 - math.cos(self.angle))
        
        total_energy = ke + pe
        
        # 最大到達点では w=0 なので E = m g r (1 - cos(max_theta))
        # 1 - cos(max_theta) = E / (m g r)
        # cos(max_theta) = 1 - E / (m g r)
        
        # 回転に必要なエネルギー閾値
        potential_max = self.mass * self.gravity * current_r * 2.0 # 最上点
        
        if total_energy >= potential_max:
            # 回転モード
            return math.pi
        else:
            # 振り子モード
            val = 1.0 - total_energy / (self.mass * self.gravity * current_r)
            val = max(-1.0, min(1.0, val)) # クランプ
            return math.acos(val)

    def check_timing_bonus(self):
        """
        タイミングボーナスのチェック（シンプル版）
        方針：最下点（角度0）付近で「縮む（Bend）」と加速。
        """
        # フィードバックタイマーをリセット
        self.timing_feedback_timer = TIMING_FEEDBACK_DURATION

        # 角度を正規化 (-pi ~ pi, 0が真下)
        current_angle = (self.angle + math.pi) % (2 * math.pi) - math.pi
        abs_angle = abs(current_angle)
        
        # 判定閾値 (ラジアン)
        # 0.50 rad ≒ 28度 (少し広げた)
        # 0.80 rad ≒ 45度
        THRESHOLD_PERFECT = 0.50
        THRESHOLD_GOOD = 0.80

        if self.is_bent:
            # 「縮む」アクション (スペースキーを押した)
            # 最下点付近で縮むのが正解
            if abs_angle < THRESHOLD_PERFECT:
                self.timing_quality = "perfect"
                self.combo += 1
                return True
            elif abs_angle < THRESHOLD_GOOD:
                self.timing_quality = "good"
                self.combo = 0 # コンボ切れ
                return True
            else:
                self.timing_quality = "poor"
                self.combo = 0
                return False
        else:
            # 「伸ばす」アクション (スペースキーを離した)
            
            # リリース操作は基本的に「失敗」扱いにしない（ストレス軽減）
            # ただし、物理的には最下点で伸ばすと減速する（角運動量保存）
            
            if abs_angle > THRESHOLD_GOOD:
                self.timing_quality = "good" # 理想的なリリース
                self.timing_feedback_timer = TIMING_FEEDBACK_DURATION
                return True
            elif abs_angle > THRESHOLD_PERFECT:
                self.timing_quality = "good"
                self.timing_feedback_timer = TIMING_FEEDBACK_DURATION
                return True
            else:
                # 最下点付近でのリリース（Safe Release）
                # 直前の判定がPerfectなら、それを維持する（表示を上書きしない）
                # タップ操作（押してすぐ離す）の時にPerfectがGoodで消されるのを防ぐ
                if self.timing_quality == "perfect" and self.timing_feedback_timer > 0:
                    return True
                
                self.timing_quality = "good"
                self.timing_feedback_timer = TIMING_FEEDBACK_DURATION
                return True

    def release(self):
        """
        鉄棒から離す（赤ボタン＝Enterキーで呼ばれる）
        """
        # どんな速さでも離せるように変更
        if not self.released:
            self.released = True

            # 現在の位置と速度を計算
            effective_length = self.arm_length * self.bent_ratio
            self.pos_x = self.bar_x + effective_length * math.sin(self.angle)
            self.pos_y = self.bar_y + effective_length * math.cos(self.angle)

            # 放物運動の初速度を設定（接線方向の速度）
            # 円運動の接線方向: 位置ベクトル(sin, cos)に対して垂直方向
            # 速度ベクトル = 角速度 × 半径 × 接線方向単位ベクトル
            speed = abs(self.angular_velocity) * effective_length

            # 接線方向の単位ベクトル（angular_velocityの符号を考慮）
            if self.angular_velocity > 0:
                # 反時計回り: 接線方向は (cos(angle), -sin(angle))
                tangent_x = math.cos(self.angle)
                tangent_y = -math.sin(self.angle)
            else:
                # 時計回り: 接線方向は (-cos(angle), sin(angle))
                tangent_x = -math.cos(self.angle)
                tangent_y = math.sin(self.angle)

            # 初速度を設定（飛距離を伸ばすため2.0倍のブースト）
            velocity_boost = 2.0

            # 回転数ボーナス（より多く回転した方が飛距離が伸びる）
            rotation_bonus = 1.0 + (self.rotation_count * 0.2)  # 回転1回ごとに20%増加

            # 最終的な初速度
            self.velocity_x = speed * tangent_x * velocity_boost * rotation_bonus
            self.velocity_y = speed * tangent_y * velocity_boost * rotation_bonus

    def update(self):
        """物理演算の更新"""
        if self.landed:
            return

        if not self.released:
            # 鉄棒にぶら下がっている状態
            self.update_swing()
        else:
            # 放物運動
            self.update_flight()
        
        # 軌跡の更新（視覚効果のみ）
        self.update_trail()

    def update_trail(self):
        """軌跡データの更新"""
        # 現在の重心位置を取得
        if not self.released:
            effective_length = self.arm_length * self.bent_ratio
            x = self.bar_x + effective_length * math.sin(self.angle)
            y = self.bar_y + effective_length * math.cos(self.angle)
        else:
            x = self.pos_x
            y = self.pos_y
            
        self.trail.append((x, y))
        if len(self.trail) > MAX_TRAIL_LENGTH:
            self.trail.pop(0)

    def update_swing(self):
        """
        振り子運動の更新
        慣性モーメント変化と角運動量保存を実装
        """
        # タイミングフィードバックタイマーを減少
        if self.timing_feedback_timer > 0:
            self.timing_feedback_timer -= 1

        # 屈伸率の変化を計算（慣性モーメント計算のために古い値を保存）
        old_moment = self.moment_of_inertia_extended * (0.4 + 0.6 * self.bent_ratio)

        # bent_ratioの変化を適用
        self.bent_ratio += (self.target_bent_ratio - self.bent_ratio) * TRANSITION_SPEED

        # 新しい慣性モーメント
        current_moment = self.moment_of_inertia_extended * (0.4 + 0.6 * self.bent_ratio)

        # 角運動量保存: L = I * ω
        if abs(old_moment) > 0.001 and abs(current_moment - old_moment) > 0.01:
            self.angular_velocity = (old_moment * self.angular_velocity) / current_moment

        # 重力によるトルク: τ = m * g * r * sin(θ)
        effective_length = self.arm_length * self.bent_ratio
        gravity_torque = -self.mass * self.gravity * effective_length * math.sin(self.angle)

        # 角加速度: α = τ / I
        angular_acceleration = gravity_torque / current_moment

        # 高速回転時の加速抑制係数（大車輪中の急加速を防ぐ）
        speed_dampener = 1.0
        if abs(self.angular_velocity) > 0.15:
            # 0.15を超えると加速効果が徐々に落ちる（最大で元の20%まで）
            speed_dampener = max(0.2, 1.0 - (abs(self.angular_velocity) - 0.15) * 4.0)

        # タイミング品質に応じてエネルギーを追加（直前の屈伸動作の評価）
        # コンボに応じて加速力を変化（徐々に速く）
        if self.timing_feedback_timer > 0:
            if self.timing_quality == "perfect":
                # コンボボーナス: 基礎値は低め、コンボで上昇（上限あり）
                combo_bonus = min(self.combo * ENERGY_BOOST_COMBO_BONUS, ENERGY_BOOST_COMBO_MAX)
                energy_boost = (ENERGY_BOOST_PERFECT_BASE + combo_bonus) * speed_dampener

                angular_acceleration += energy_boost * (1 if self.angular_velocity > 0 else -1)
            elif self.timing_quality == "good":
                # 良いタイミング
                energy_boost = ENERGY_BOOST_GOOD * speed_dampener
                angular_acceleration += energy_boost * (1 if self.angular_velocity > 0 else -1)
            elif self.timing_quality == "poor":
                # 悪いタイミング：エネルギーロス
                angular_acceleration += ENERGY_LOSS_POOR * (1 if self.angular_velocity > 0 else -1)

        # 角速度を更新
        self.angular_velocity += angular_acceleration
        self.angular_velocity *= self.damping  # 空気抵抗による減衰

        # 角度を更新
        self.angle += self.angular_velocity

        # 回転数のカウント
        if self.last_angle < 0 and self.angle >= 0:
            self.rotation_count += 1
        self.last_angle = self.angle

        # 体の角度を更新（アニメーション用）
        self.body_angle = self.angle

    def update_flight(self):
        """放物運動の更新"""
        # 重力を適用
        self.velocity_y += GRAVITY_FLIGHT

        # 空気抵抗（わずかな減衰）
        self.velocity_x *= AIR_RESISTANCE
        self.velocity_y *= AIR_RESISTANCE

        # 位置を更新
        self.pos_x += self.velocity_x
        self.pos_y += self.velocity_y

        # 回転（空中でも回転し続ける、少し減衰）
        self.body_angle += self.angular_velocity * 0.4
        self.angular_velocity *= 0.98  # 空中での回転も減衰

    def get_momentum_for_display(self):
        """
        UI表示用の勢いを取得

        Returns:
            勢いの値（0-3の範囲）
        """
        # 角速度の大きさを勢いとして返す
        momentum = abs(self.angular_velocity) * 20
        return min(momentum, 3.0)

    def draw(self, screen, cam=None, show_guide=False):
        """選手を描画（画像ベース）"""
        if not self.released and show_guide:
            self.draw_guide_bar(screen)

        self._draw_trail(screen, cam)

        # 画像がある場合は画像で描画
        if self.img_body_extended and self.img_body_bent:
            self._draw_body_with_image(screen, cam)

    def draw_guide_bar(self, screen):
        """画面左側にタイミングガイドバーを描画（シンプル固定スケール版）"""
        # バーの設定
        bar_x = 30
        bar_y = 150
        bar_w = 20
        bar_h = 300
        center_y = bar_y + bar_h // 2
        
        # 背景
        bar_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(screen, (40, 44, 52), bar_rect, border_radius=10)
        
        # 中央線（最下点 TARGET）
        pygame.draw.line(screen, (200, 200, 200), (bar_x - 5, center_y), (bar_x + bar_w + 5, center_y), 2)
        
        # 表示スケール: バーの端を ±120度 (2/3 pi) とする
        SCALE_RANGE = math.pi * 0.66 
        
        def get_y(ang):
            # ang: -SCALE ~ +SCALE
            ratio = ang / SCALE_RANGE
            # 前回のUIに合わせる: 上半分: 右振れ (+angle), 下半分: 左振れ (-angle)
            # 画面Y座標は上が小さいので、+ratio -> 上(-offset)
            ratio = max(-1.0, min(1.0, ratio))
            return center_y - ratio * (bar_h / 2)

        # 判定エリアの描画
        # PERFECTゾーン (±28度以内)
        THRESHOLD_PERFECT = 0.50
        p_top = get_y(THRESHOLD_PERFECT)
        p_btm = get_y(-THRESHOLD_PERFECT)
        p_rect = pygame.Rect(bar_x, p_top, bar_w, p_btm - p_top)
        pygame.draw.rect(screen, PERFECT_ZONE_COLOR, p_rect)
        
        # GOODゾーン (±45度以内) - PERFECTの外側
        THRESHOLD_GOOD = 0.80
        # 上側
        g_top = get_y(THRESHOLD_GOOD)
        g_btm = p_top
        pygame.draw.rect(screen, GUIDE_ZONE_COLOR, (bar_x, g_top, bar_w, g_btm - g_top))
        # 下側
        g_top_neg = p_btm
        g_btm_neg = get_y(-THRESHOLD_GOOD)
        pygame.draw.rect(screen, GUIDE_ZONE_COLOR, (bar_x, g_top_neg, bar_w, g_btm_neg - g_top_neg))

        # カーソル (現在位置)
        current_angle = (self.angle + math.pi) % (2 * math.pi) - math.pi
        cursor_y = get_y(current_angle)
        
        # カーソル色
        c_color = (255, 255, 255)
        if p_top <= cursor_y <= p_btm:
            c_color = (255, 255, 0) # 黄色エリア内
        
        # カーソル描画
        pygame.draw.circle(screen, c_color, (bar_x + bar_w // 2, int(cursor_y)), 8)
        pygame.draw.circle(screen, (0, 0, 0), (bar_x + bar_w // 2, int(cursor_y)), 8, 1)

    def _draw_body_with_image(self, screen, cam):
        """画像を使って体を描画"""
        # 使用する画像を選択（is_bentに応じて）
        body_img = self.img_body_bent if self.is_bent else self.img_body_extended

        # スケール計算
        cam_scale = cam['scale'] if cam else 1.0

        # 画像のサイズを調整（適切なサイズに）
        # ターゲットの高さを設定（ゲーム内の単位で約160px）
        target_height = 160 * cam_scale
        
        original_width = body_img.get_width()
        original_height = body_img.get_height()
        
        # アスペクト比を維持してスケーリング
        if original_height > 0:
            scale_factor = target_height / original_height
            scaled_width = int(original_width * scale_factor)
            scaled_height = int(target_height)
        else:
            scaled_width = int(original_width * cam_scale)
            scaled_height = int(original_height * cam_scale)

        if scaled_width > 0 and scaled_height > 0:
            scaled_img = pygame.transform.smoothscale(body_img, (scaled_width, scaled_height))

            # 回転角度を計算（body_angleをdegreeに変換）
            # body_angleは鉄棒からの角度（ラジアン）
            # Pygameの回転は反時計回りが正
            # 座標系: 0が真下(Y+), 時計回り(+)で左(-X)?? 
            # 前回の考察: 
            # angle=0(Down). angle increases -> CCW (Right/Up). 
            # Pygame rotation: +degrees is CCW.
            # So if angle increases (Right swing), we want image to rotate CCW (Feet Right).
            # So use positive degrees.
            angle_deg = math.degrees(self.body_angle)

            # 画像を回転
            rotated_img = pygame.transform.rotate(scaled_img, angle_deg)

            # 手（回転中心）の位置を計算（ワールド座標）
            if not self.released:
                # 鉄棒にぶら下がっている：手の位置＝鉄棒の位置
                hand_x = self.bar_x
                hand_y = self.bar_y
            else:
                # 空中：重心(pos)から手の位置を逆算
                # 重心は pos_x, pos_y
                # 手の位置 = 重心 - (物理的な腕の長さ * 方向ベクトル)
                effective_length = ARM_LENGTH * self.bent_ratio
                hand_x = self.pos_x - effective_length * math.sin(self.angle)
                hand_y = self.pos_y - effective_length * math.cos(self.angle)

            # スクリーン座標に変換
            hand_screen_pos = self._to_screen(hand_x, hand_y, cam)

            # 回転後の描画位置（中心）を計算
            # 画像上の「手」の位置（上端中央）を、スクリーン上のhand_screen_posに合わせる
            
            # 画像中心から手（上端）へのベクトル (スクリーン座標系：Y下、上はマイナス)
            offset_center_to_hand = pygame.math.Vector2(0, -scaled_height / 2)
            
            # ベクトルを回転
            # スクリーン上の回転(angle_deg: 時計回りが負)と、Vector2.rotate(反時計回りが正)の整合
            # スクリーン上で上(0,-1)を右(1,0)にするには-90度回転。
            # Vector2(0,-1)を(1,0)にするには+90度回転。
            # よって符号を反転させる
            offset_rotated = offset_center_to_hand.rotate(-angle_deg)
            
            # 画像の中心座標 = 手のスクリーン座標 - 回転したオフセット
            center_pos = pygame.math.Vector2(hand_screen_pos) - offset_rotated
            
            # 描画
            rect = rotated_img.get_rect(center=(int(center_pos.x), int(center_pos.y)))
            screen.blit(rotated_img, rect)

    def _to_screen(self, x, y, cam):
        """ワールド座標をスクリーン座標に変換"""
        if cam:
            return (x * cam['scale'] + cam['ox'], y * cam['scale'] + cam['oy'])
        return (x, y)

    def _draw_trail(self, screen, cam):
        """軌跡（残像）を描画"""
        if len(self.trail) <= 1:
            return

        scale = cam['scale'] if cam else 1.0

        for i in range(len(self.trail) - 1):
            start_pos = self._to_screen(*self.trail[i], cam)
            end_pos = self._to_screen(*self.trail[i + 1], cam)
            alpha = int(255 * (i / len(self.trail)) * 0.4)
            width = max(1, int(10 * scale))
            pygame.draw.line(screen, TRAIL_COLOR[:3], start_pos, end_pos, width)

