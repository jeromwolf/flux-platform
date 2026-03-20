// ---------------------------------------------------------------------------
// Unique constraints for the Maritime Knowledge Graph
// All statements are idempotent (IF NOT EXISTS).
// ---------------------------------------------------------------------------

CREATE CONSTRAINT vessel_mmsi IF NOT EXISTS FOR (v:Vessel) REQUIRE v.mmsi IS UNIQUE;
CREATE CONSTRAINT vessel_imo IF NOT EXISTS FOR (v:Vessel) REQUIRE v.imo IS UNIQUE;
CREATE CONSTRAINT port_unlocode IF NOT EXISTS FOR (p:Port) REQUIRE p.unlocode IS UNIQUE;
CREATE CONSTRAINT regulation_code IF NOT EXISTS FOR (r:Regulation) REQUIRE r.code IS UNIQUE;
CREATE CONSTRAINT organization_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.orgId IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.docId IS UNIQUE;
CREATE CONSTRAINT datasource_id IF NOT EXISTS FOR (ds:DataSource) REQUIRE ds.sourceId IS UNIQUE;
CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.serviceId IS UNIQUE;
CREATE CONSTRAINT experiment_id IF NOT EXISTS FOR (e:Experiment) REQUIRE e.experimentId IS UNIQUE;
CREATE CONSTRAINT test_facility_id IF NOT EXISTS FOR (f:TestFacility) REQUIRE f.facilityId IS UNIQUE;
CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (i:Incident) REQUIRE i.incidentId IS UNIQUE;
CREATE CONSTRAINT sensor_id IF NOT EXISTS FOR (s:Sensor) REQUIRE s.sensorId IS UNIQUE;

// ----- RBAC Access Control -----
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.userId IS UNIQUE;
CREATE CONSTRAINT role_id IF NOT EXISTS FOR (r:Role) REQUIRE r.roleId IS UNIQUE;
CREATE CONSTRAINT dataclass_id IF NOT EXISTS FOR (dc:DataClass) REQUIRE dc.classId IS UNIQUE;
CREATE CONSTRAINT permission_id IF NOT EXISTS FOR (p:Permission) REQUIRE p.permissionId IS UNIQUE;

// ----- KRISO Research -----
CREATE CONSTRAINT dataset_id IF NOT EXISTS FOR (ds:ExperimentalDataset) REQUIRE ds.datasetId IS UNIQUE;
CREATE CONSTRAINT model_ship_id IF NOT EXISTS FOR (ms:ModelShip) REQUIRE ms.modelId IS UNIQUE;
CREATE CONSTRAINT measurement_id IF NOT EXISTS FOR (m:Measurement) REQUIRE m.measurementId IS UNIQUE;

// ----- Additional unique identifiers -----
CREATE CONSTRAINT voyage_id IF NOT EXISTS FOR (v:Voyage) REQUIRE v.voyageId IS UNIQUE;
CREATE CONSTRAINT track_segment_id IF NOT EXISTS FOR (ts:TrackSegment) REQUIRE ts.segmentId IS UNIQUE;
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.personId IS UNIQUE;
CREATE CONSTRAINT workflow_id IF NOT EXISTS FOR (w:Workflow) REQUIRE w.workflowId IS UNIQUE;
CREATE CONSTRAINT ai_model_id IF NOT EXISTS FOR (m:AIModel) REQUIRE m.modelId IS UNIQUE;
