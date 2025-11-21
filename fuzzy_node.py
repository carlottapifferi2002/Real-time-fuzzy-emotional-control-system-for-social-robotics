#!/usr/bin/env python3
import sys
import os
import rospy
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from emotional_manager import EmotionalManager
from dynamic_reconfigure.client import Client
from parameters import get_planner_params

EXPRESSION_MAP = {
    "neutral": 0,
    "happy": 1,
    "sad": 2,
    "surprise": 3,
    "disgust": 4,
    "fear": 5,
    "angry": 6
}

class FuzzyNode:
    def __init__(self, config_dir, personality):
        self.manager = EmotionalManager(config_dir, personality=personality)
        self.last_face_value = None
        self.current_vel_x = 0.0
        # Variabili per debug
        self.last_expr_str = "neutral"
        self.last_mood_val = 50.0
        self.last_speed_val = 0.3
        self.last_mood_label = "standard"
        self.last_speed_label = "standard"
        self.last_alertness_val = 50.0
        self.last_alertness_label = "standard"
        self.last_tuning_val = 50.0
        self.last_tuning_label = "medium"
             
        rospy.init_node("fuzzy_emotional_node", anonymous=True)
                
        self.mood_pub = rospy.Publisher("/fuzzy_mood", String, queue_size=10)
        self.speed_pub = rospy.Publisher("/fuzzy_body_speed", String, queue_size=10)
        self.alertness_pub = rospy.Publisher("/fuzzy_alertness", String, queue_size=10)
        self.tuning_pub = rospy.Publisher("/fuzzy_tuning", String, queue_size=10)
        self.pal_client = Client("/move_base/PalLocalPlanner", timeout=10)
                
        rospy.Subscriber("/expression_detected", String, self.expression_callback)
        rospy.Subscriber("/mobile_base_controller/odom", Odometry, self.odom_callback)
        rospy.loginfo(f"FuzzyNode started with personality: {personality} and listening to /expression_detected")

    def odom_callback(self, msg):
        self.current_vel_x = msg.twist.twist.linear.x

    def expression_callback(self, msg):
        expr_str = msg.data.lower()
        if expr_str not in EXPRESSION_MAP:
            rospy.logwarn(f"Espressione '{expr_str}' non riconosciuta.")
            return
        face_value = EXPRESSION_MAP[expr_str]

        if face_value == self.last_face_value:
            # La faccia è uguale alla precedente: non ricalcolo, ma esco
            return
        self.last_face_value = face_value

        # Scegli la velocità attuale da usare come input per il fuzzy:
        current_speed = self.current_vel_x

        outputs = self.manager.compute({
            "face": face_value,
            "body_speed": current_speed
        })
        mood_val = outputs["mood"]
        speed_val = outputs["body_speed"]
        alertness_val = outputs["alertness"]
        tuning_val = outputs["tuning"]

        mood_label = self.manager.controllers["mood"].mapOutput(mood_val)
        speed_label = self.manager.controllers["body_speed"].mapOutput(speed_val)
        alertness_label = self.manager.controllers["alertness"].mapOutput(alertness_val)
        tuning_label = self.manager.controllers["tuning"].mapOutput(tuning_val)

        # Salva le ultime variabili per poterle visualizzare sempre nel loop
        self.last_expr_str = expr_str
        self.last_mood_val = mood_val
        self.last_speed_val = speed_val
        self.last_mood_label = mood_label
        self.last_speed_label = speed_label
        self.last_alertness_val = alertness_val
        self.last_alertness_label = alertness_label
        self.last_tuning_val = tuning_val
        self.last_tuning_label = tuning_label

        self.mood_pub.publish(mood_label if mood_label else str(mood_val))
        self.speed_pub.publish(speed_label if speed_label else str(speed_val))
        self.alertness_pub.publish(alertness_label if alertness_label else str(alertness_val))
        self.tuning_pub.publish(tuning_label if tuning_label else str(tuning_val))
                
        # --- LOG DETTAGLIATO ---
        rospy.loginfo("==== Fuzzy Debug ====")
        rospy.loginfo(f"Espressione rilevata: {expr_str} (valore: {face_value})")
        rospy.loginfo(f"body_speed input: {current_speed:.3f} m/s")
        rospy.loginfo(f"mood output: {mood_val:.2f} ({mood_label})")
        rospy.loginfo(f"body_speed output: {speed_val:.3f} ({speed_label})")
        rospy.loginfo(f"alertness output: {alertness_val:.2f} ({alertness_label})")
        rospy.loginfo(f"tuning output: {tuning_val:.2f} ({tuning_label})")
        
        # Tuning dinamico PalLocalPlanner
        try:
            max_vel_x = speed_val
            
            # Mappatura di tuning_label su max_vel_theta e security_dist
            max_vel_theta, security_dist = get_planner_params(tuning_label)
            
            self.pal_client.update_configuration({
                "max_vel_theta": max_vel_theta,
                "security_dist": security_dist,
                "max_vel_x": max_vel_x
            })
            rospy.loginfo(
                f"Set PalLocalPlanner: max_vel_theta={max_vel_theta:.2f}, "
                f"security_dist={security_dist:.3f}, max_vel_x={max_vel_x:.2f} (tuning: {tuning_label})"
            )
        except Exception as e:
            rospy.logwarn(f"Dynamic reconfigure non riuscito: {e}")

    def run(self):
        rate = rospy.Rate(10)  # 10Hz
        while not rospy.is_shutdown():
            rospy.loginfo(
                f"Face: {self.last_expr_str} | "
                f"Mood: {self.last_mood_val:.2f} ({self.last_mood_label}) | "
                f"BodySpeed: {self.last_speed_val:.2f} ({self.last_speed_label}) | "
                f"Alertness: {self.last_alertness_val:.2f} ({self.last_alertness_label}) | "
                f"Tuning: {self.last_tuning_val:.2f} ({self.last_tuning_label})"
            )
            rospy.loginfo(
                f"Velocità attuale della base: {self.current_vel_x:.3f} m/s"
            )
            rate.sleep()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(script_dir, "controllers")
    
    # Scegli la personalità
    if len(sys.argv) > 1:
        personality = sys.argv[1].lower()
        if personality not in ["shy", "intense"]:
            print("Personalità non valida! Usa 'shy' o 'intense'.")
            sys.exit(1)
    else:
        personality = "shy"    # default
    
    node = FuzzyNode(config_dir, personality)
    node.run()
