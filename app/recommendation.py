"""Recommendation System for Trainer Marketplace"""
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import User, Booking, Review
from collections import defaultdict

class RecommendationEngine:
    def __init__(self, db: Session):
        self.db = db

    def get_recommendations_for_user(self, user_id: int, limit: int = 6):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return self._get_trending_trainers(limit)

        content_scores = self._content_based_scores(user)
        collab_scores = self._collaborative_scores(user_id)
        trending_scores = self._trending_scores()

        all_ids = set(content_scores.keys()) | set(collab_scores.keys()) | set(trending_scores.keys())
        final_scores = {}
        for tid in all_ids:
            score = (content_scores.get(tid, 0) * 0.50 + 
                     collab_scores.get(tid, 0) * 0.35 + 
                     trending_scores.get(tid, 0) * 0.15)
            final_scores[tid] = score

        trainers = self.db.query(User).filter(
            User.id.in_(list(final_scores.keys())),
            User.role == "trainer", User.status == "active",
            User.showcase_until > datetime.utcnow()
        ).all()

        for t in trainers:
            t.rec_score = round(final_scores.get(t.id, 0), 2)
            t.rec_reason = self._get_reason(t, user, content_scores, collab_scores)

        trainers.sort(key=lambda x: x.rec_score, reverse=True)
        return trainers[:limit]

    def _content_based_scores(self, user):
        scores = defaultdict(float)
        trainers = self.db.query(User).filter(
            User.role == "trainer", User.status == "active",
            User.showcase_until > datetime.utcnow()
        ).all()
        for trainer in trainers:
            score = 0.0
            trainer_discs = [d.lower() for d in (trainer.disciplines or [])]
            if trainer.specialization:
                trainer_discs.append(trainer.specialization.lower())
            if user.preferred_sport:
                pref = user.preferred_sport.lower()
                if pref in trainer_discs:
                    score += 0.4
                elif any(pref in d for d in trainer_discs):
                    score += 0.25
            goal_map = {"learn_basics": ["toprope", "bouldering", "kids"],
                       "improve_technique": ["bouldering", "lead", "training"],
                       "grade_progression": ["lead", "bouldering", "training", "trad"],
                       "competition_prep": ["speed", "bouldering", "lead", "training"],
                       "outdoor_transition": ["trad", "multipitch", "lead", "ice"],
                       "kids_coaching": ["kids", "toprope", "bouldering"]}
            trainer_discs = list(trainer.disciplines or [])
            if trainer.specialization:
                trainer_discs.append(trainer.specialization.lower())
            if user.fitness_goal and trainer_discs:
                if set(goal_map.get(user.fitness_goal, [])) & set(trainer_discs):
                    score += 0.3
            if user.budget_max and trainer.hourly_rate:
                if trainer.hourly_rate <= user.budget_max:
                    score += 0.2 * (1 - (trainer.hourly_rate / user.budget_max) * 0.5)
            exp_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
            user_exp = exp_map.get(user.experience_level, 1)
            if trainer.experience_years:
                if user_exp == 1 and trainer.experience_years >= 2: score += 0.1
                elif user_exp == 2 and trainer.experience_years >= 3: score += 0.1
                elif user_exp == 3 and trainer.experience_years >= 5: score += 0.08
            score += trainer.verification_level * 0.05
            if trainer.rating: score += (trainer.rating / 5.0) * 0.1
            scores[trainer.id] = min(score, 1.0)
        return scores

    def _collaborative_scores(self, user_id):
        scores = defaultdict(float)
        user_bookings = self.db.query(Booking).filter(Booking.client_id == user_id).all()
        user_trainer_ids = {b.trainer_id for b in user_bookings}
        for tid in user_trainer_ids:
            bookings = self.db.query(Booking).filter(Booking.trainer_id == tid).all()
            for b in bookings:
                if b.client_id != user_id:
                    scores[b.client_id] += 1
        for sim_uid, similarity in list(scores.items()):
            sim_bookings = self.db.query(Booking).filter(Booking.client_id == sim_uid).all()
            for b in sim_bookings:
                if b.trainer_id not in user_trainer_ids:
                    scores[b.trainer_id] = scores.get(b.trainer_id, 0) + similarity * 0.15
        return scores

    def _trending_scores(self):
        scores = defaultdict(float)
        trainers = self.db.query(User).filter(
            User.role == "trainer", User.status == "active",
            User.showcase_until > datetime.utcnow()
        ).all()
        for t in trainers:
            if t.total_bookings > 0:
                scores[t.id] = min(t.total_bookings / 50.0, 0.5)
            if t.rating and t.rating >= 4.5: scores[t.id] += 0.2
        return scores

    def _get_trending_trainers(self, limit):
        trainers = self.db.query(User).filter(
            User.role == "trainer", User.status == "active",
            User.showcase_until > datetime.utcnow()
        ).order_by(User.rating.desc(), User.total_bookings.desc()).limit(limit).all()
        for t in trainers:
            t.rec_score = round((t.rating / 5.0) * 0.7 + min(t.total_bookings / 100, 0.3), 2)
            t.rec_reason = "Популярный тренер"
        return trainers

    def _get_reason(self, trainer, user, content_scores, collab_scores):
        from app.climbing import discipline_name
        reasons = []
        if user.preferred_sport:
            trainer_discs = [d.lower() for d in (trainer.disciplines or [])]
            if trainer.specialization:
                trainer_discs.append(trainer.specialization.lower())
            if user.preferred_sport.lower() in trainer_discs:
                reasons.append("Дисциплина: %s" % discipline_name(user.preferred_sport.lower()))
        if trainer.rating and trainer.rating >= 4.5: reasons.append(f"Рейтинг {trainer.rating}")
        if collab_scores.get(trainer.id, 0) > 0: reasons.append("Похожие клиенты выбирают")
        if trainer.verification_level >= 2: reasons.append("Верифицирован")
        if not reasons: reasons.append("Рекомендуем для вас")
        return " | ".join(reasons[:2])

    def update_user_interests(self, user_id):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user: return
        bookings = self.db.query(Booking).filter(Booking.client_id == user_id).all()
        interests = defaultdict(int)
        for b in bookings:
            trainer = self.db.query(User).filter(User.id == b.trainer_id).first()
            if trainer: interests[trainer.specialization] = interests.get(trainer.specialization, 0) + 1
        user.interests_vector = dict(interests)
        self.db.commit()

def get_recommendation_engine(db: Session):
    return RecommendationEngine(db)
