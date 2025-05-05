"""
Validation logic for DPP AAS and Submodels.
"""

from typing import Dict, Any, List, Tuple, Optional

from basyx.aas import model
from basyx.aas.model import Submodel, SubmodelElementCollection, Property, File, ReferenceElement, RelationshipElement
from basyx.aas import datatypes
from pydantic import BaseModel, Field, ValidationError, validator, field_validator

# --- Helper: BaSyx to Dict Conversion ---

def basyx_element_to_dict(element: model.SubmodelElement) -> Optional[Dict[str, Any]]:
    """Converts a BaSyx SubmodelElement to a dictionary for validation."""
    if isinstance(element, model.Property):
        return {
            "idShort": element.id_short,
            "value": element.value,
            "valueType": datatypes.XSD_TYPE_NAMES.get(element.value_type, "unknown"),
            # Optionally add semanticId, description, qualifiers if needed for validation
        }
    elif isinstance(element, model.SubmodelElementCollection):
        collection_dict = {
            "idShort": element.id_short,
            # Optionally add semanticId, description
            "elements": {}
        }
        for sub_elem in element.submodel_element:
            sub_elem_dict = basyx_element_to_dict(sub_elem)
            if sub_elem_dict:
                collection_dict["elements"][sub_elem.id_short] = sub_elem_dict
        return collection_dict
    elif isinstance(element, model.File):
        return {
            "idShort": element.id_short,
            "value": element.value, # Path to the file
            "contentType": element.content_type,
            "valueType": "file", # Custom type for validation
        }
    # TODO: Add conversion for other types like ReferenceElement, RelationshipElement if needed
    return None # Skip unsupported types for now

def basyx_submodel_to_dict(submodel_obj: model.Submodel) -> Dict[str, Any]:
    """Converts a BaSyx Submodel object to a dictionary for validation."""
    submodel_data = {
        "idShort": submodel_obj.id_short,
        # Optionally add semanticId, kind, description
        "submodelElements": {}
    }
    for elem in submodel_obj.submodel_element:
        elem_dict = basyx_element_to_dict(elem)
        if elem_dict:
            submodel_data["submodelElements"][elem.id_short] = elem_dict
    return submodel_data


# --- Validation Error --- 

class ValidationErrorDetail(BaseModel):
    loc: Tuple[str, ...] = Field(..., description="Location of the error in the data structure")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")

class DPPValidationError(Exception):
    """Custom exception for DPP validation errors."""
    def __init__(self, message: str, errors: List[ValidationErrorDetail] = None):
        super().__init__(message)
        self.errors = errors or []

    def __str__(self):
        error_details = "\n".join([f"  - {e.loc}: {e.msg} ({e.type})" for e in self.errors])
        return f"{super().__str__()}\nDetails:\n{error_details}"

# --- Base Validator --- 

def validate_data(data: Dict[str, Any], model_cls: type[BaseModel]) -> Tuple[bool, List[ValidationErrorDetail]]:
    """
    Validates dictionary data against a Pydantic model.

    Args:
        data: The dictionary data to validate.
        model_cls: The Pydantic model class to validate against.

    Returns:
        A tuple containing a boolean indicating validity and a list of validation errors (if any).
    """
    try:
        model_cls.model_validate(data)
        return True, []
    except ValidationError as e:
        errors = [ValidationErrorDetail(loc=err["loc"], msg=err["msg"], type=err["type"]) for err in e.errors()]
        return False, errors

# --- Submodel Specific Validators (using Pydantic) --- 

# Example: Nameplate Submodel Validation Model
class NameplateProperty(BaseModel):
    idShort: str
    value: str
    valueType: str = "string" # Default or validate
    # semanticId: Optional[Dict] # Could add validation for semanticId structure

class NameplateSubmodelElements(BaseModel):
    ManufacturerName: NameplateProperty
    ManufacturerProductDesignation: NameplateProperty
    YearOfConstruction: NameplateProperty
    SerialNumber: Optional[NameplateProperty] = None
    BatchNumber: Optional[NameplateProperty] = None
    # Add other optional/required properties based on spec

class NameplateSubmodelData(BaseModel):
    idShort: str = "Nameplate"
    # semanticId: Optional[Dict] # Validate semanticId structure
    submodelElements: NameplateSubmodelElements

# TODO: Define Pydantic models for other submodels:
# - TechnicalDataSubmodelData
# - MaterialCompositionSubmodelData
# - CarbonFootprintSubmodelData (PCF and TCF structures)

# Technical Data Submodel Validation Model
class TechnicalDataProperty(BaseModel):
    idShort: str
    value: float # Assuming float based on typical technical data
    valueType: str = "double" # Default or validate

class TechnicalDataSubmodelElements(BaseModel):
    Density: Optional[TechnicalDataProperty] = None
    MeltFlowIndex: Optional[TechnicalDataProperty] = None
    ProcessingTemperature: Optional[TechnicalDataProperty] = None
    # Add other properties as needed

class TechnicalDataSubmodelData(BaseModel):
    idShort: str = "TechnicalData"
    submodelElements: TechnicalDataSubmodelElements

# Material Composition Submodel Validation Model
class MaterialCompositionProperty(BaseModel):
    idShort: str
    value: Any # Can be string, float, etc.
    valueType: str # Validate based on property

class MaterialCompositionSubmodelElements(BaseModel):
    MaterialName: Optional[MaterialCompositionProperty] = None
    PolymerType: Optional[MaterialCompositionProperty] = None
    RecycledContent: Optional[MaterialCompositionProperty] = None # Often percentage (float)
    MaterialColor: Optional[MaterialCompositionProperty] = None
    MaterialSource: Optional[MaterialCompositionProperty] = None
    BioBasedContent: Optional[MaterialCompositionProperty] = None # Often percentage (float)
    Additives: Optional[MaterialCompositionProperty] = None # Could be a list or complex structure
    # Add other properties as needed

class MaterialCompositionSubmodelData(BaseModel):
    idShort: str = "MaterialComposition"
    submodelElements: MaterialCompositionSubmodelElements

# Carbon Footprint Submodel Validation Model
class PCFProperty(BaseModel):
    idShort: str
    value: Any # Type depends on property (string, double, date)
    valueType: str

class PCFElements(BaseModel):
    # Define expected properties directly here, matching keys in smc_data["elements"]
    PCFCalculationMethod: Optional[PCFProperty] = None
    PCFCO2eq: Optional[PCFProperty] = None
    PCFReferenceValueForCalculation: Optional[PCFProperty] = None
    PCFQuantityOfMeasureForCalculation: Optional[PCFProperty] = None
    PCFLifeCyclePhase: Optional[PCFProperty] = None
    PublicationDate: Optional[PCFProperty] = None
    ExpirationDate: Optional[PCFProperty] = None
    # TODO: Add ExplanatoryStatement (File) and PCFGoodsAddressHandover (SMC)

class PCFSubmodelElementCollectionData(BaseModel):
    idShort: str # e.g., ProductCarbonFootprint00
    # semanticId: Optional[Dict] # Validate semanticId structure
    elements: PCFElements # Validate the nested elements structure

class TCFElements(BaseModel):
    # Define expected properties directly here
    TCFCalculationMethod: Optional[PCFProperty] = None
    TCFCO2eq: Optional[PCFProperty] = None
    TCFReferenceValueForCalculation: Optional[PCFProperty] = None
    # TODO: Add other TCF properties

class TCFSubmodelElementCollectionData(BaseModel):
    idShort: str # e.g., TransportCarbonFootprint00
    # semanticId: Optional[Dict] # Validate semanticId structure
    elements: TCFElements # Validate the nested elements structure

class CarbonFootprintSubmodelElements(BaseModel):
    # Use Dict to capture multiple PCF/TCF instances
    # Key would be the idShort like "ProductCarbonFootprint00"
    # Value would be the validated SMC data (PCFSubmodelElementCollectionData or TCFSubmodelElementCollectionData)
    # Pydantic validation for dynamic keys is complex, maybe validate SMCs individually
    pass # Keep validation separate as implemented in validate_submodel

class CarbonFootprintSubmodelData(BaseModel):
    idShort: str = "CarbonFootprint"
    # semanticId: Optional[Dict] # Validate semanticId structure
    submodelElements: CarbonFootprintSubmodelElements # Basic check for the elements container


# --- Main Validation Function --- 

def validate_submodel(submodel_obj: model.Submodel) -> Tuple[bool, List[ValidationErrorDetail]]:
    """
    Validates a BaSyx Submodel object against known Pydantic models.

    Args:
        submodel_obj: The BaSyx Submodel object.

    Returns:
        A tuple containing a boolean indicating validity and a list of validation errors (if any).
    """
    all_errors: List[ValidationErrorDetail] = []
    is_valid = True

    # Select the appropriate Pydantic model for the overall submodel structure
    model_cls = None
    if submodel_obj.id_short == "Nameplate":
        model_cls = NameplateSubmodelData
    elif submodel_obj.id_short == "TechnicalData":
        model_cls = TechnicalDataSubmodelData
    elif submodel_obj.id_short == "MaterialComposition":
        model_cls = MaterialCompositionSubmodelData
    elif submodel_obj.id_short == "CarbonFootprint":
        model_cls = CarbonFootprintSubmodelData # Basic validation of the SM itself
    else:
        # Unknown submodel type, skip detailed validation
        return True, []

    # Convert the full submodel including elements for element-level validation
    submodel_full_data = basyx_submodel_to_dict(submodel_obj)

    # Validate the main submodel structure using the selected Pydantic model
    try:
        model_cls.model_validate(submodel_full_data)
    except ValidationError as e:
        is_valid = False
        errors = [ValidationErrorDetail(loc=err["loc"], msg=err["msg"], type=err["type"]) for err in e.errors()]
        all_errors.extend(errors)

    # Special handling for CarbonFootprint SMCs - validate each SMC individually
    if submodel_obj.id_short == "CarbonFootprint":
        for elem in submodel_obj.submodel_element:
            if isinstance(elem, model.SubmodelElementCollection):
                smc_data = basyx_element_to_dict(elem)
                smc_model_cls = None
                # Determine which SMC model to use based on semantic ID
                # Note: Need to import the semantic IDs from carbon_footprint.py or a constants file
                # Assuming SEM_ID_PRODUCT_CARBON_FOOTPRINT_SMC and SEM_ID_TRANSPORT_CARBON_FOOTPRINT_SMC are available
                try:
                    # Placeholder check - replace with actual semantic ID comparison
                    if "ProductCarbonFootprint" in elem.id_short: # elem.semantic_id == SEM_ID_PRODUCT_CARBON_FOOTPRINT_SMC:
                        smc_model_cls = PCFSubmodelElementCollectionData
                    elif "TransportCarbonFootprint" in elem.id_short: # elem.semantic_id == SEM_ID_TRANSPORT_CARBON_FOOTPRINT_SMC:
                         smc_model_cls = TCFSubmodelElementCollectionData
                except AttributeError:
                     # Handle cases where semantic_id might be missing or comparison fails
                     pass 
                
                if smc_model_cls and smc_data:
                    try:
                        # Validate the SMC dictionary structure (including the nested 'elements')
                        smc_model_cls.model_validate(smc_data)
                    except ValidationError as e_smc:
                        is_valid = False
                        # Adjust location to reflect nesting within the submodel
                        smc_errors = [ValidationErrorDetail(loc=(submodel_obj.id_short, elem.id_short) + err["loc"], msg=err["msg"], type=err["type"]) for err in e_smc.errors()]
                        all_errors.extend(smc_errors)

    return is_valid, all_errors

# TODO:
# 1. Implement robust BaSyx object to Dict conversion.
# 2. Define Pydantic models for all required submodels (TechnicalData, MaterialComposition, CarbonFootprint).
# 3. Implement validation for SubmodelElementCollections within CarbonFootprint.
# 4. Integrate `validate_submodel` into `dpp_service.py` create/update methods.
# 5. Consider adding validation for AAS Shell structure itself.


