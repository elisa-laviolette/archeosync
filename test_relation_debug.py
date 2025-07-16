#!/usr/bin/env python3
"""
Debug script to understand QGIS relation creation issues.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from qgis.core import QgsProject, QgsRelation, QgsVectorLayer, QgsApplication
    print("QGIS imports successful")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Set up the QGIS application
QgsApplication.setPrefixPath("/Applications/QGIS-LTR.app/Contents/MacOS", True)  # Adjust path if needed
qgs = QgsApplication([], False)
qgs.initQgis()

def test_simple_relation_creation():
    """Test creating a simple relation between two layers."""
    print("Testing simple relation creation...")
    
    # Create a new project
    project = QgsProject()
    
    # Create two simple layers
    layer1 = QgsVectorLayer("Point?crs=EPSG:4326&field=id:integer&field=name:string", "Layer1", "memory")
    layer2 = QgsVectorLayer("Point?crs=EPSG:4326&field=id:integer&field=ref_id:integer", "Layer2", "memory")
    
    if not layer1.isValid() or not layer2.isValid():
        print("Failed to create test layers")
        return False
    
    # Add layers to project
    project.addMapLayer(layer1)
    project.addMapLayer(layer2)
    
    print(f"Layer1 ID: {layer1.id()}")
    print(f"Layer2 ID: {layer2.id()}")
    print(f"Layer1 valid: {layer1.isValid()}")
    print(f"Layer2 valid: {layer2.isValid()}")
    
    # Create a relation
    relation = QgsRelation()
    relation.setId("test_relation")
    relation.setName("Test Relation")
    relation.setReferencingLayer(layer2.id())
    relation.setReferencedLayer(layer1.id())
    relation.addFieldPair("ref_id", "id")
    
    print(f"Relation valid after setup: {relation.isValid()}")
    print(f"Relation referencing layer: {relation.referencingLayerId()}")
    print(f"Relation referenced layer: {relation.referencedLayerId()}")
    print(f"Relation field pairs: {relation.fieldPairs()}")
    
    # Try to add the relation
    relation_manager = project.relationManager()
    success = relation_manager.addRelation(relation)
    
    print(f"Successfully added relation: {success}")
    print(f"Relations in project: {list(relation_manager.relations().keys())}")
    
    return success

def test_relation_with_geopackage_layers():
    """Test creating relations with Geopackage layers."""
    print("\nTesting relation creation with Geopackage layers...")
    
    # Create a new project
    project = QgsProject()
    
    # Create Geopackage layers (this would be similar to what we're doing in the field project)
    layer1_path = "/tmp/test_layer1.gpkg"
    layer2_path = "/tmp/test_layer2.gpkg"
    
    # Create simple Geopackage layers
    layer1 = QgsVectorLayer(f"Point?crs=EPSG:4326&field=id:integer&field=name:string", "Layer1", "memory")
    layer2 = QgsVectorLayer(f"Point?crs=EPSG:4326&field=id:integer&field=ref_id:integer", "Layer2", "memory")
    
    if not layer1.isValid() or not layer2.isValid():
        print("Failed to create test Geopackage layers")
        return False
    
    # Add layers to project
    project.addMapLayer(layer1)
    project.addMapLayer(layer2)
    
    print(f"Layer1 ID: {layer1.id()}")
    print(f"Layer2 ID: {layer2.id()}")
    print(f"Layer1 valid: {layer1.isValid()}")
    print(f"Layer2 valid: {layer2.isValid()}")
    
    # Create a relation
    relation = QgsRelation()
    relation.setId("test_gpkg_relation")
    relation.setName("Test Geopackage Relation")
    relation.setReferencingLayer(layer2.id())
    relation.setReferencedLayer(layer1.id())
    relation.addFieldPair("ref_id", "id")
    
    print(f"Relation valid after setup: {relation.isValid()}")
    print(f"Relation referencing layer: {relation.referencingLayerId()}")
    print(f"Relation referenced layer: {relation.referencedLayerId()}")
    print(f"Relation field pairs: {relation.fieldPairs()}")
    
    # Try to add the relation
    relation_manager = project.relationManager()
    success = relation_manager.addRelation(relation)
    
    print(f"Successfully added relation: {success}")
    print(f"Relations in project: {list(relation_manager.relations().keys())}")
    
    return success

if __name__ == "__main__":
    print("Starting QGIS relation debug tests...")
    
    # Test 1: Simple memory layers
    success1 = test_simple_relation_creation()
    
    # Test 2: Geopackage-like layers
    success2 = test_relation_with_geopackage_layers()
    
    print(f"\nTest results:")
    print(f"Simple relation creation: {'SUCCESS' if success1 else 'FAILED'}")
    print(f"Geopackage relation creation: {'SUCCESS' if success2 else 'FAILED'}")
    
    if not success1 or not success2:
        print("\nThis suggests there might be an issue with QGIS relation creation in this environment.")
        print("The field project relation creation might be failing due to similar issues.")

    # Clean up QGIS application
    qgs.exitQgis() 