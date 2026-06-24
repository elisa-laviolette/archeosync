"""
Tests for import validation feature copying (batched, default-value aware).
"""

import sys
import unittest
from unittest.mock import Mock, patch

try:
    from qgis.PyQt import QtWidgets
    from services.import_validation_service import (
        FEATURE_LOAD_YIELD_EVERY,
        ImportFeatureCopier,
        LayerCopyJob,
        LayerFieldMapping,
        _feature_id,
        build_layer_copy_jobs,
        build_peer_temp_layer_replacements,
        load_job_source_features_chunk,
        remove_pending_import_layers,
        reset_import_session_tracking,
        TEMPORARY_IMPORT_LAYER_NAMES,
        IMPORT_LAYER_MAPPINGS,
        DEFAULT_COPY_BATCH_SIZE,
    )
except ImportError:
    from qgis.PyQt import QtWidgets
    from ..services.import_validation_service import (
        FEATURE_LOAD_YIELD_EVERY,
        ImportFeatureCopier,
        LayerCopyJob,
        LayerFieldMapping,
        _feature_id,
        build_layer_copy_jobs,
        build_peer_temp_layer_replacements,
        load_job_source_features_chunk,
        remove_pending_import_layers,
        reset_import_session_tracking,
        TEMPORARY_IMPORT_LAYER_NAMES,
        IMPORT_LAYER_MAPPINGS,
        DEFAULT_COPY_BATCH_SIZE,
    )


class TestImportFeatureCopier(unittest.TestCase):
    """Unit tests for ImportFeatureCopier."""

    def setUp(self):
        if QtWidgets.QApplication.instance() is None:
            self._qt_app = QtWidgets.QApplication(sys.argv if sys.argv else ["test"])

    def test_copy_batch_inserts_features_one_at_a_time(self):
        """Each feature is added individually so sequential defaults stay correct."""
        copier = ImportFeatureCopier(batch_size=2)
        source_features = [Mock(), Mock(), Mock()]
        target_layer = Mock()
        target_layer.isEditable.return_value = True
        target_layer.addFeature.return_value = True

        with patch.object(
            copier,
            "create_feature_with_target_structure",
            side_effect=lambda *_args, **_kwargs: Mock(),
        ):
            result = copier.copy_features_batch(
                source_features=source_features,
                target_layer=target_layer,
                start_index=0,
                field_mapping=Mock(attribute_field_pairs=[]),
            )

        self.assertEqual(target_layer.addFeature.call_count, 2)
        target_layer.addFeatures.assert_not_called()
        self.assertEqual(result.copied_count, 2)
        self.assertEqual(result.next_index, 2)

    def test_copy_batch_yields_ui_between_batches(self):
        """Each batch should cooperatively yield to the Qt event loop."""
        copier = ImportFeatureCopier(batch_size=1)
        source_features = [Mock()]
        target_layer = Mock()
        target_layer.isEditable.return_value = True
        added = Mock()
        added.id.return_value = 1
        target_layer.addFeature.return_value = True

        with patch.object(copier, "create_feature_with_target_structure", return_value=Mock()), \
             patch("services.import_validation_service.maybe_yield_to_ui") as mock_yield:
            copier.copy_features_batch(
                source_features=source_features,
                target_layer=target_layer,
                start_index=0,
                field_mapping=Mock(attribute_field_pairs=[]),
            )

        mock_yield.assert_called()

    def test_feature_id_accepts_edit_buffer_fids(self):
        """Temporary edit-buffer FIDs are negative and must be kept for selection."""
        buffer_feature = Mock()
        buffer_feature.id.return_value = -7
        self.assertEqual(_feature_id(buffer_feature), -7)

        unassigned = Mock()
        unassigned.id.return_value = -1
        self.assertIsNone(_feature_id(unassigned))

    def test_select_copied_features_uses_select_by_ids(self):
        """Selection after copy should use a single selectByIds call."""
        target_layer = Mock()
        ImportFeatureCopier.select_copied_features(target_layer, [-3, -2, -1, 10])
        target_layer.removeSelection.assert_called_once()
        target_layer.selectByIds.assert_called_once()
        selected_ids = target_layer.selectByIds.call_args[0][0]
        self.assertEqual(selected_ids, [-3, -2, 10])
        target_layer.select.assert_not_called()

    def test_select_copied_features_on_real_edit_buffer_layer(self):
        """Copied features in edit mode should end up selected on the definitive layer."""
        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer

        target_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=name:string",
            "definitive",
            "memory",
        )
        self.assertTrue(target_layer.isValid())
        target_layer.startEditing()

        added_ids = []
        for label in ("A", "B"):
            feature = QgsFeature(target_layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1.0, 2.0)))
            feature.setAttribute("name", label)
            self.assertTrue(target_layer.addFeature(feature))
            fid = _feature_id(feature)
            self.assertIsNotNone(fid)
            self.assertLess(fid, 0)
            added_ids.append(fid)

        ImportFeatureCopier.select_copied_features(target_layer, added_ids)
        self.assertEqual(set(target_layer.selectedFeatureIds()), set(added_ids))


class TestImportFeatureCopierQgis(unittest.TestCase):
    """QGIS-backed tests for default value replay (moved from dialog tests)."""

    def setUp(self):
        if QtWidgets.QApplication.instance() is None:
            self._qt_app = QtWidgets.QApplication(sys.argv if sys.argv else ["test"])
        self.copier = ImportFeatureCopier()

    def test_case_insensitive_field_matching_csv_points(self):
        from qgis.core import QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer
        from qgis.PyQt.QtCore import QVariant

        temp_fields = QgsFields()
        temp_fields.append(QgsField("pointid", QVariant.String))
        temp_feature = QgsFeature(temp_fields)
        temp_feature.setAttribute("pointid", "TS001")
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100.0, 200.0)))

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=PointID:string",
            "Total Station Points",
            "memory",
        )
        self.assertTrue(def_layer.isValid())

        mapping = self.copier.build_field_mapping(temp_feature.fields(), def_layer)
        new_feature = self.copier.create_feature_with_target_structure(
            temp_feature, def_layer, mapping
        )

        self.assertEqual(new_feature["PointID"], "TS001")

    def test_apply_layer_default_value_when_source_field_missing(self):
        from qgis.core import QgsDefaultValue, QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer
        from qgis.PyQt.QtCore import QVariant

        temp_fields = QgsFields()
        temp_fields.append(QgsField("pointid", QVariant.String))
        temp_feature = QgsFeature(temp_fields)
        temp_feature.setAttribute("pointid", "TS001")
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100.0, 200.0)))

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=PointID:string&field=operation_id:integer",
            "Total Station Points",
            "memory",
        )
        self.assertTrue(def_layer.isValid())
        operation_idx = def_layer.fields().indexOf("operation_id")
        def_layer.setDefaultValueDefinition(operation_idx, QgsDefaultValue("6"))

        mapping = self.copier.build_field_mapping(temp_feature.fields(), def_layer)
        new_feature = self.copier.create_feature_with_target_structure(
            temp_feature, def_layer, mapping
        )

        self.assertEqual(new_feature["PointID"], "TS001")
        self.assertEqual(new_feature["operation_id"], 6)

    def test_self_referencing_default_preserves_imported_integer(self):
        from qgis.core import (
            QgsDefaultValue,
            QgsFeature,
            QgsFields,
            QgsField,
            QgsGeometry,
            QgsPointXY,
            QgsVectorLayer,
        )
        from qgis.PyQt.QtCore import QVariant

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=object_id:string&field=square_meter_id:integer",
            "Objects",
            "memory",
        )
        self.assertTrue(def_layer.isValid())
        square_idx = def_layer.fields().indexOf("square_meter_id")
        def_layer.setDefaultValueDefinition(
            square_idx,
            QgsDefaultValue(
                'CASE WHEN "square_meter_id" IS NULL THEN 3 ELSE "square_meter_id" END'
            ),
        )

        temp_fields = QgsFields()
        temp_fields.append(QgsField("object_id", QVariant.String))
        temp_fields.append(QgsField("square_meter_id", QVariant.Int))
        temp_feature = QgsFeature(temp_fields)
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1.0, 2.0)))
        temp_feature.setAttribute("object_id", "OBJ-1")
        temp_feature.setAttribute("square_meter_id", 7)

        mapping = self.copier.build_field_mapping(temp_feature.fields(), def_layer)
        new_feature = self.copier.create_feature_with_target_structure(
            temp_feature, def_layer, mapping
        )

        self.assertEqual(new_feature["object_id"], "OBJ-1")
        self.assertEqual(new_feature["square_meter_id"], 7)

    def test_sequential_defaults_increment_sequence(self):
        """Each copied feature should receive an incremented default sequence value."""
        from qgis.core import (
            QgsDefaultValue,
            QgsFeature,
            QgsFields,
            QgsField,
            QgsGeometry,
            QgsPointXY,
            QgsVectorLayer,
        )
        from qgis.PyQt.QtCore import QVariant

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=pointid:string&field=sequence:integer",
            "Total Station Points",
            "memory",
        )
        self.assertTrue(def_layer.isValid())
        sequence_idx = def_layer.fields().indexOf("sequence")
        def_layer.setDefaultValueDefinition(
            sequence_idx, QgsDefaultValue('maximum("sequence") + 1')
        )

        def_layer.startEditing()
        existing = QgsFeature(def_layer.fields())
        existing.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1.0, 2.0)))
        existing.setAttribute("pointid", "P1")
        existing.setAttribute("sequence", 3)
        def_layer.addFeature(existing)
        def_layer.commitChanges()

        temp_fields = QgsFields()
        temp_fields.append(QgsField("pointid", QVariant.String))
        temp_feature_a = QgsFeature(temp_fields)
        temp_feature_a.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100.0, 200.0)))
        temp_feature_a.setAttribute("pointid", "TS-A")
        temp_feature_b = QgsFeature(temp_fields)
        temp_feature_b.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(101.0, 201.0)))
        temp_feature_b.setAttribute("pointid", "TS-B")

        mapping = self.copier.build_field_mapping(temp_fields, def_layer)
        def_layer.startEditing()

        batch_result = self.copier.copy_features_batch(
            source_features=[temp_feature_a, temp_feature_b],
            target_layer=def_layer,
            start_index=0,
            field_mapping=mapping,
        )
        self.assertEqual(batch_result.copied_count, 1)
        batch_result = self.copier.copy_features_batch(
            source_features=[temp_feature_a, temp_feature_b],
            target_layer=def_layer,
            start_index=batch_result.next_index,
            field_mapping=mapping,
        )
        self.assertEqual(batch_result.copied_count, 1)

        values = []
        for feature in def_layer.getFeatures():
            if feature["pointid"] in ("TS-A", "TS-B"):
                values.append(feature["sequence"])
        self.assertEqual(sorted(values), [4, 5])


class TestLoadJobSourceFeaturesChunk(unittest.TestCase):
    """Tests for incremental temporary-layer loading."""

    def test_load_job_source_features_chunk_loads_incrementally(self):
        features = [Mock(), Mock(), Mock(), Mock(), Mock()]
        source_layer = Mock()
        source_layer.getFeatures.return_value = iter(features)

        job = LayerCopyJob(
            temp_layer_name="New Objects",
            definitive_layer_key="objects_layer",
            source_layer=source_layer,
            target_layer=Mock(),
            field_mapping=LayerFieldMapping(attribute_field_pairs=[]),
            feature_count=5,
        )

        self.assertFalse(load_job_source_features_chunk(job, chunk_size=2))
        self.assertEqual(len(job.source_features), 2)
        self.assertFalse(job.load_complete)

        self.assertFalse(load_job_source_features_chunk(job, chunk_size=2))
        self.assertEqual(len(job.source_features), 4)

        self.assertTrue(load_job_source_features_chunk(job, chunk_size=2))
        self.assertEqual(len(job.source_features), 5)
        self.assertTrue(job.load_complete)
        self.assertEqual(job.feature_count, 5)


class TestBuildLayerCopyJobs(unittest.TestCase):
    """Tests for resolving temporary/definitive layer pairs."""

    def test_build_layer_copy_jobs_resolves_configured_layers(self):
        mock_fields = Mock()
        mock_fields.count.return_value = 0
        mock_feature = Mock()
        mock_feature.fields.return_value = mock_fields

        temp_objects = Mock()
        temp_objects.name.return_value = "New Objects"
        temp_objects.featureCount.return_value = 1
        temp_objects.fields.return_value = mock_fields
        temp_objects.getFeatures.return_value = [mock_feature]

        def_objects = Mock()
        def_objects.id.return_value = "objects_def_id"
        def_objects.fields.return_value = mock_fields

        project_layers = {
            "tmp": temp_objects,
            "def": def_objects,
        }

        def get_setting(key, default=""):
            if key == "objects_layer":
                return "objects_def_id"
            return default

        jobs = build_layer_copy_jobs(project_layers, get_setting)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].temp_layer_name, "New Objects")
        self.assertIs(jobs[0].source_layer, temp_objects)
        self.assertIs(jobs[0].target_layer, def_objects)
        self.assertEqual(jobs[0].feature_count, 1)
        self.assertIsNone(jobs[0].source_features)


class TestBuildPeerTempLayerReplacements(unittest.TestCase):
    """Tests for mapping definitive layers to active temporary import layers."""

    def test_build_peer_temp_layer_replacements_maps_configured_pairs(self):
        temp_objects = Mock()
        temp_objects.name.return_value = "New Objects"
        temp_objects.id.return_value = "temp_objects_id"

        def_objects = Mock()
        def_objects.id.return_value = "def_objects_id"

        project_layers = {
            "temp": temp_objects,
            "def": def_objects,
        }

        def get_setting(key, default=""):
            if key == "objects_layer":
                return "def_objects_id"
            return default

        replacements = build_peer_temp_layer_replacements(
            project_layers,
            get_setting,
        )

        self.assertEqual(
            replacements,
            {"def_objects_id": "temp_objects_id"},
        )


class TestRemovePendingImportLayers(unittest.TestCase):
    """Tests for cleaning up temporary import layers between sessions."""

    def test_remove_pending_import_layers_deletes_known_temp_layers(self):
        temp_layer = Mock()
        temp_layer.name.return_value = "New Objects"
        temp_layer.id.return_value = "temp_objects_id"

        other_layer = Mock()
        other_layer.name.return_value = "Recording Areas"
        other_layer.id.return_value = "areas_id"

        project = Mock()
        project.mapLayers.return_value = {
            "temp_objects_id": temp_layer,
            "areas_id": other_layer,
        }

        layer_service = Mock()
        layer_service.remove_import_clone_relations.return_value = 0
        layer_service.repair_definitive_project_relations.return_value = 0

        removed = remove_pending_import_layers(
            project,
            layer_service=layer_service,
            get_setting=lambda key, default="": default,
        )

        self.assertEqual(removed, 1)
        project.removeMapLayer.assert_called_once_with("temp_objects_id")
        layer_service.invalidate_layer_cache.assert_called_once_with("temp_objects_id")

    def test_temporary_import_layer_names_match_mappings(self):
        self.assertEqual(
            set(TEMPORARY_IMPORT_LAYER_NAMES),
            set(IMPORT_LAYER_MAPPINGS.keys()),
        )


class TestResetImportSessionTracking(unittest.TestCase):
    """Tests for clearing import bookkeeping after cancellation."""

    def test_reset_import_session_tracking_clears_services(self):
        csv_service = Mock()
        project_service = Mock()
        layer_service = Mock()

        reset_import_session_tracking(
            csv_import_service=csv_service,
            field_project_import_service=project_service,
            layer_service=layer_service,
        )

        csv_service.clear_last_imported_files.assert_called_once()
        project_service.clear_last_imported_projects.assert_called_once()
        layer_service.clear_caches.assert_called_once()


if __name__ == "__main__":
    unittest.main()
