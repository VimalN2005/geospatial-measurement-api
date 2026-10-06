import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from threading import Lock

class StorageRepository:
    """Thread-safe SQLite repository for persistent storage of uploaded files and measurements."""

    def __init__(self, db_path: str = "uploads/geospatial_api.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.lock:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        file_type TEXT NOT NULL,
                        feature_count INTEGER NOT NULL,
                        crs TEXT NOT NULL,
                        status TEXT NOT NULL,
                        projected_crs TEXT,
                        projection_strategy TEXT,
                        summary_json TEXT,
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS features (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        feature_index INTEGER NOT NULL,
                        feature_identifier TEXT,
                        geometry_type TEXT NOT NULL,
                        geometry_geojson TEXT NOT NULL,
                        properties_json TEXT NOT NULL,
                        measurement_type TEXT NOT NULL,
                        measurements_json TEXT,
                        FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
                    )
                """)
                conn.commit()

    def save_file_record(self, file_data: Dict[str, Any]):
        with self.lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO files 
                    (id, filename, file_type, feature_count, crs, status, projected_crs, projection_strategy, summary_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_data["id"],
                    file_data["filename"],
                    file_data["file_type"],
                    file_data["feature_count"],
                    file_data["crs"],
                    file_data["status"],
                    file_data.get("projected_crs"),
                    file_data.get("projection_strategy"),
                    json.dumps(file_data.get("summary", {}))
                ))
                conn.commit()

    def save_features(self, file_id: str, features: List[Dict[str, Any]]):
        with self.lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM features WHERE file_id = ?", (file_id,))
                for feat in features:
                    conn.execute("""
                        INSERT INTO features 
                        (file_id, feature_index, feature_identifier, geometry_type, geometry_geojson, properties_json, measurement_type, measurements_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        file_id,
                        feat["feature_index"],
                        feat.get("feature_id"),
                        feat["geometry_type"],
                        json.dumps(feat.get("geometry", {})),
                        json.dumps(feat.get("properties", {})),
                        feat["measurement_type"],
                        json.dumps(feat.get("measurements")) if feat.get("measurements") else None
                    ))
                conn.commit()

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("summary_json"):
                res["summary"] = json.loads(res["summary_json"])
            return res

    def list_files(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM files ORDER BY uploaded_at DESC")
            rows = cur.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get("summary_json"):
                    item["summary"] = json.loads(item["summary_json"])
                result.append(item)
            return result

    def get_features(self, file_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM features WHERE file_id = ? ORDER BY feature_index ASC", (file_id,))
            rows = cur.fetchall()
            features = []
            for r in rows:
                features.append({
                    "feature_index": r["feature_index"],
                    "feature_id": r["feature_identifier"],
                    "geometry_type": r["geometry_type"],
                    "geometry": json.loads(r["geometry_geojson"]),
                    "properties": json.loads(r["properties_json"]),
                    "measurement_type": r["measurement_type"],
                    "measurements": json.loads(r["measurements_json"]) if r["measurements_json"] else None
                })
            return features

    def delete_file(self, file_id: str) -> bool:
        with self.lock:
            with self._get_connection() as conn:
                cur = conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
                conn.execute("DELETE FROM features WHERE file_id = ?", (file_id,))
                conn.commit()
                return cur.rowcount > 0

storage = StorageRepository()
