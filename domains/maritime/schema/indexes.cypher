// ---------------------------------------------------------------------------
// Indexes for the Maritime Knowledge Graph
// All statements are idempotent (IF NOT EXISTS).
// ---------------------------------------------------------------------------

// ---- Vector indexes (multimodal embeddings) ----

CREATE VECTOR INDEX visual_embedding IF NOT EXISTS FOR (n:Observation) ON (n.visualEmbedding) OPTIONS {indexConfig: {`vector.dimensions`: 512, `vector.similarity_function`: 'cosine'}};
CREATE VECTOR INDEX text_embedding IF NOT EXISTS FOR (n:Document) ON (n.textEmbedding) OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}};
CREATE VECTOR INDEX trajectory_embedding IF NOT EXISTS FOR (n:TrackSegment) ON (n.trajectoryEmbedding) OPTIONS {indexConfig: {`vector.dimensions`: 256, `vector.similarity_function`: 'cosine'}};
CREATE VECTOR INDEX fused_embedding IF NOT EXISTS FOR (n:Observation) ON (n.fusedEmbedding) OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

// ---- Spatial indexes (point) ----

CREATE POINT INDEX vessel_location IF NOT EXISTS FOR (v:Vessel) ON (v.currentLocation);
CREATE POINT INDEX observation_location IF NOT EXISTS FOR (o:Observation) ON (o.location);
CREATE POINT INDEX incident_location IF NOT EXISTS FOR (i:Incident) ON (i.location);
CREATE POINT INDEX port_location IF NOT EXISTS FOR (p:Port) ON (p.location);
CREATE POINT INDEX geopoint_coords IF NOT EXISTS FOR (g:GeoPoint) ON (g.coords);

// ---- Full-text indexes ----

CREATE FULLTEXT INDEX document_search IF NOT EXISTS FOR (d:Document) ON EACH [d.title, d.content, d.summary];
CREATE FULLTEXT INDEX regulation_search IF NOT EXISTS FOR (r:Regulation) ON EACH [r.title, r.description, r.code];
CREATE FULLTEXT INDEX vessel_search IF NOT EXISTS FOR (v:Vessel) ON EACH [v.name, v.callSign];
CREATE FULLTEXT INDEX port_search IF NOT EXISTS FOR (p:Port) ON EACH [p.name, p.nameEn];
CREATE FULLTEXT INDEX experiment_search IF NOT EXISTS FOR (e:Experiment) ON EACH [e.title, e.objective];

// ---- Range indexes (frequently queried properties) ----

CREATE INDEX vessel_type IF NOT EXISTS FOR (v:Vessel) ON (v.vesselType);
CREATE INDEX vessel_status IF NOT EXISTS FOR (v:Vessel) ON (v.currentStatus);
CREATE INDEX incident_type IF NOT EXISTS FOR (i:Incident) ON (i.incidentType);
CREATE INDEX incident_date IF NOT EXISTS FOR (i:Incident) ON (i.date);
CREATE INDEX observation_timestamp IF NOT EXISTS FOR (o:Observation) ON (o.timestamp);
CREATE INDEX track_anomaly IF NOT EXISTS FOR (t:TrackSegment) ON (t.anomaly);
CREATE INDEX weather_risk IF NOT EXISTS FOR (w:WeatherCondition) ON (w.riskLevel);
CREATE INDEX experiment_date IF NOT EXISTS FOR (e:Experiment) ON (e.date);

// ---- RBAC indexes ----

CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email);
CREATE INDEX user_status IF NOT EXISTS FOR (u:User) ON (u.status);
CREATE INDEX user_organization IF NOT EXISTS FOR (u:User) ON (u.organization);
CREATE INDEX role_name IF NOT EXISTS FOR (r:Role) ON (r.name);
CREATE INDEX role_level IF NOT EXISTS FOR (r:Role) ON (r.level);
CREATE INDEX dataclass_name IF NOT EXISTS FOR (dc:DataClass) ON (dc.name);
CREATE INDEX dataclass_level IF NOT EXISTS FOR (dc:DataClass) ON (dc.level);
CREATE INDEX permission_type IF NOT EXISTS FOR (p:Permission) ON (p.type);

// ---- KRISO research indexes ----

CREATE INDEX experiment_status IF NOT EXISTS FOR (e:Experiment) ON (e.status);
CREATE INDEX experiment_facility IF NOT EXISTS FOR (e:Experiment) ON (e.facilityId);
CREATE INDEX dataset_type IF NOT EXISTS FOR (ds:ExperimentalDataset) ON (ds.dataType);
CREATE INDEX measurement_type IF NOT EXISTS FOR (m:Measurement) ON (m.measurementType);
CREATE INDEX model_ship_hull IF NOT EXISTS FOR (ms:ModelShip) ON (ms.hullForm);
CREATE INDEX facility_type IF NOT EXISTS FOR (tf:TestFacility) ON (tf.facilityType);

// ---- Additional operational indexes ----

CREATE INDEX voyage_status IF NOT EXISTS FOR (v:Voyage) ON (v.status);
CREATE INDEX document_type IF NOT EXISTS FOR (d:Document) ON (d.docType);
CREATE INDEX document_source IF NOT EXISTS FOR (d:Document) ON (d.source);
CREATE INDEX organization_type IF NOT EXISTS FOR (o:Organization) ON (o.orgType);
CREATE INDEX person_role IF NOT EXISTS FOR (p:Person) ON (p.role);

// ---- Fulltext indexes (additional) ----

CREATE FULLTEXT INDEX facility_search IF NOT EXISTS FOR (tf:TestFacility) ON EACH [tf.name, tf.nameEn];
CREATE FULLTEXT INDEX organization_search IF NOT EXISTS FOR (o:Organization) ON EACH [o.name, o.nameEn];
CREATE FULLTEXT INDEX dataset_search IF NOT EXISTS FOR (ds:ExperimentalDataset) ON EACH [ds.title, ds.description];
