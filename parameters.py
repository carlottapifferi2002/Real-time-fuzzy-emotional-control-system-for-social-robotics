def get_planner_params(tuning_label):
    """
    Restituisce (max_vel_theta, security_dist) in base al tuning_label.
    Puoi modificare qui i parametri per renderli facilmente configurabili.
    """
    mapping = {
        "low":    (0.5,  0.5),
        "medium": (0.75, 0.3),
        "high":   (1.0,  0.15)
    }
    # fallback: medium se label non riconosciuta
    return mapping.get(tuning_label, (0.75, 0.3))
