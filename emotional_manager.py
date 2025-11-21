from fuzzy_core import FuzzyControllerBase
import os
import time
import sys

# # Numeric-to-label mapping for expressions
EXPRESSION_INV = {
    0: "neutral",
    1: "happy",
    2: "sad",
    3: "surprise",
    4: "disgust",
    5: "fear",
    6: "angry"
}

class EmotionalManager:
    # transient boost
    
    def __init__(self, config_dir, personality="shy"):
        self.personality = personality
        self.state = {
            "mood": 50.0,
            "body_speed": 0.3,
            "alertness": 50.0,
            "tuning": 50.0,
            "face": 0
        }

        # Load the existing controllers (no modifications to the controllers’ JSON files)
        self.controllers = {
            "mood": FuzzyControllerBase(os.path.join(config_dir, f"mood_{personality}.json")),
            "body_speed": FuzzyControllerBase(os.path.join(config_dir, f"body_speed_{personality}.json")),
            "alertness": FuzzyControllerBase(os.path.join(config_dir, f"alertness_{personality}.json")),
            "tuning": FuzzyControllerBase(os.path.join(config_dir, f"tuning_{personality}.json")),
        }

        # State of the transient boost (decays over time)
        # speed_initial: initial delta applied to the speed
        # steps_left, total_steps: uration in iterations (linear decay)
        self.boost_state = {
            "speed_initial": 0.0,
            "steps_left": 0,
            "total_steps": 0
        }

        # Speed clamp limits (se vuoi modificarli)
        self.min_speed = 0.0
        self.max_speed = 1.0

        # Default boost definitions per emotion, per personality
        # The values represent additive deltas on body_speed and their duration (in steps)
        if self.personality == "intense":
            self._boosts = {
                "happy":    {"speed": 0.25,  "steps": 4},
                "sad":      {"speed": -0.12, "steps": 3},
                "fear":     {"speed": -0.30, "steps": 4},
                "angry":    {"speed": -0.18, "steps": 3},
                "surprise": {"speed": 0.12,  "steps": 2},
                "disgust":  {"speed": -0.10, "steps": 2},
                "neutral":  {"speed": 0.0,   "steps": 0}
            }
        else:  # shy
            self._boosts = {
                "happy":    {"speed": 0.12,  "steps": 3},
                "sad":      {"speed": -0.08, "steps": 2},
                "fear":     {"speed": -0.18, "steps": 3},
                "angry":    {"speed": -0.12, "steps": 2},
                "surprise": {"speed": 0.07,  "steps": 2},
                "disgust":  {"speed": -0.06, "steps": 1},
                "neutral":  {"speed": 0.0,   "steps": 0}
            }

        # traccia l'ultima faccia per attivare il boost solo quando cambia
        self._last_face = None

    def _prepare_inputs(self, controller, candidates):
        """
        Builds the input dictionary to pass to controller.compute(),
        using only the keys expected by the controller (controller.inputs).
        """
        inputs = {}
        for key, val in candidates.items():
            if key in controller.inputs:
                inputs[key] = val
        return inputs

    def trigger_boost_for_face(self, face_value):
        """Activates the boost associated with the facial label, if defined."""
        label = EXPRESSION_INV.get(int(face_value), "neutral")
        cfg = self._boosts.get(label)
        if not cfg:
            return
        self.boost_state["speed_initial"] = float(cfg.get("speed", 0.0))
        self.boost_state["steps_left"] = int(cfg.get("steps", 0))
        self.boost_state["total_steps"] = int(cfg.get("steps", 0))

    def _apply_and_decay_boosts(self, outputs):
        """Applies the boost to the resulting body_speed (linear decay)."""
        bs = self.boost_state
        if bs["steps_left"] > 0 and bs["total_steps"] > 0:
            factor = bs["steps_left"] / float(bs["total_steps"])  # linear
            delta = bs["speed_initial"] * factor
            outputs["body_speed"] = outputs.get("body_speed", 0.0) + delta
            # clamp for safety
            outputs["body_speed"] = max(self.min_speed, min(self.max_speed, outputs["body_speed"]))

            bs["steps_left"] -= 1
            if bs["steps_left"] <= 0:
                bs["speed_initial"] = 0.0
                bs["steps_left"] = 0
                bs["total_steps"] = 0

        return outputs

    def compute(self, inputs):
        # update the face in the state
        if "face" in inputs:
            self.state["face"] = inputs["face"]

        # if the face has changed, trigger the boost for that emotion
        if self._last_face is None or self.state["face"] != self._last_face:
            self.trigger_boost_for_face(self.state["face"])
            self._last_face = self.state["face"]

        
        # Mood
        mood_candidates = {
            "face": self.state["face"],
            "_face": self.state["face"],
            "mood": self.state["mood"],
            "_mood": self.state["mood"]
        }
        mood_in = self._prepare_inputs(self.controllers["mood"], mood_candidates)
        if mood_in:
            try:
                self.state["mood"] = self.controllers["mood"].compute(mood_in)
            except Exception:
                pass

        # body_speed: use the actual velocity if provided as input, otherwise the previous one
        if "body_speed" in inputs:
            speed_input = inputs["body_speed"]
        else:
            speed_input = self.state["body_speed"]

        bs_candidates = {
            "mood": self.state["mood"],
            "_mood": self.state["mood"],
            "body_speed": speed_input,
            "_body_speed": speed_input
        }
        bs_in = self._prepare_inputs(self.controllers["body_speed"], bs_candidates)
        if bs_in:
            try:
                self.state["body_speed"] = self.controllers["body_speed"].compute(bs_in)
            except Exception:
                pass

        # Alertness
        a_candidates = {
            "face": self.state["face"],
            "_face": self.state["face"],
            "alertness": self.state["alertness"],
            "_alertness": self.state["alertness"]
        }
        a_in = self._prepare_inputs(self.controllers["alertness"], a_candidates)
        if a_in:
            try:
                self.state["alertness"] = self.controllers["alertness"].compute(a_in)
            except Exception:
                pass

        # Tuning
        t_candidates = {
            "alertness": self.state["alertness"],
            "_alertness": self.state["alertness"],
            "tuning": self.state["tuning"],
            "_tuning": self.state["tuning"]
        }
        t_in = self._prepare_inputs(self.controllers["tuning"], t_candidates)
        if t_in:
            try:
                self.state["tuning"] = self.controllers["tuning"].compute(t_in)
            except Exception:
                pass

        # Prepare outputs from the fuzzy results
        outputs = {
            "mood": self.state["mood"],
            "body_speed": self.state["body_speed"],
            "alertness": self.state["alertness"],
            "tuning": self.state["tuning"]
        }

        # Apply the transient boost ONLY to the velocity (decaying)
        outputs = self._apply_and_decay_boosts(outputs)

        # Update the state with the final outputs
        self.state["mood"] = outputs["mood"]
        self.state["body_speed"] = outputs["body_speed"]
        self.state["alertness"] = outputs["alertness"]
        self.state["tuning"] = outputs["tuning"]

        return outputs


if __name__ == "__main__":
    config_dir = os.path.dirname(__file__) + "/controllers"
    if len(sys.argv) > 1:
        personality = sys.argv[1].lower()
        if personality not in ["shy", "intense"]:
            print("Invalid personality! Use ‘shy’ or ‘intense’.")
            sys.exit(1)
    else:
        personality = "shy"

    manager = EmotionalManager(config_dir, personality=personality)

    # quick test
    face_sequence = [0, 1, 2, 3, 4, 5, 6, 1, 0]  # neutral -> happy -> sad -> ...
    idx = 0
    while True:
        current_inputs = {"face": face_sequence[idx % len(face_sequence)]}
        outputs = manager.compute(current_inputs)
        face_label = EXPRESSION_INV[current_inputs["face"]]
        print(f"Input face: {face_label} | Outputs: {outputs}")
        idx += 1
        time.sleep(0.5)
