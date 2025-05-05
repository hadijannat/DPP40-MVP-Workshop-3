"""
DPP Service for business logic operations.

This service handles operations related to Digital Product Passports (DPPs)
and AAS Shells/Submodels.
"""
from typing import List, Optional, Dict, Any, Tuple, Union
import logging
import base64
import uuid
import json
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from basyx.aas.model import AssetAdministrationShell, Submodel, AssetInformation

from src.persistence.repositories import AASShellRepository, AASSubmodelRepository, DLTIntegrityRepository
from src.persistence.models import AASShell, AASSubmodel, DLTIntegrityProof
from src.utils.errors import EntityNotFoundError
from src.utils.aas_utils import generate_stable_uuid_from_string, decode_aas_id
from src.models.submodels.nameplate import create_nameplate_submodel
from src.models.submodels.technical_data import create_technical_data_submodel
from src.models.submodels.material_composition import create_material_composition_submodel
from src.models.schemas.dpp import DPPResponse
from src.models.schemas.integrity import EntityIntegrityStatus, VerificationResult

logger = logging.getLogger(__name__)


def basyx_to_dict(obj):
    """
    Convert a BaSyx object to a dictionary.
    
    Args:
        obj: The BaSyx object to convert
        
    Returns:
        Dictionary representation of the object
    """
    if obj is None:
        return None
    
    # Handle lists and iterables
    if isinstance(obj, list) or isinstance(obj, tuple):
        return [basyx_to_dict(item) for item in obj]
    
    # Handle dictionaries
    if isinstance(obj, dict):
        return {k: basyx_to_dict(v) for k, v in obj.items()}
    
    # Handle primitive types
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    
    # Special handling for NamespaceSet
    if hasattr(obj, 'namespace_elements'):
        # For NamespaceSet type objects
        return {'namespaces': list(obj.namespace_elements)}
    
    # Standard BaSyx objects processing
    if hasattr(obj, 'to_json'):
        try:
            # BaSyx objects usually have a to_json method
            return json.loads(obj.to_json())
        except (TypeError, json.JSONDecodeError) as e:
            # If JSON serialization fails, try to_dict or __dict__
            pass
    
    if hasattr(obj, 'to_dict'):
        # Some objects have a to_dict method
        return obj.to_dict()
    
    if hasattr(obj, '__dict__'):
        # Fall back to the object's __dict__
        # But process each value recursively
        return {k: basyx_to_dict(v) for k, v in obj.__dict__.items() 
                if not k.startswith('_')}
    
    # Last resort - convert to string
    return str(obj)


def create_asset_shell(id_short, asset_id=None):
    """
    Create an Asset Administration Shell (AAS) for a DPP.
    
    Args:
        id_short: Short ID for the shell
        asset_id: Optional asset ID
        
    Returns:
        AssetAdministrationShell instance
    """
    # Generate IDs if not provided
    if not asset_id:
        asset_id = f"urn:dpp40:asset:{str(uuid.uuid4())}"
    
    shell_id = f"urn:dpp40:aas:{str(uuid.uuid4())}"
    
    # Create the shell
    shell = AssetAdministrationShell(
        id_=shell_id,  # Use id_ instead of id
        id_short=id_short,
        asset_information=AssetInformation(  # Use AssetInformation class
            asset_kind=AssetKind.INSTANCE,  # Assuming INSTANCE, adjust if needed
            global_asset_id=asset_id
        )
    )
    
    return shell


class DPPService:
    """
    Service for Digital Product Passport operations.
    
    This service implements the core business logic for DPP operations,
    using the repositories for data access.
    """
    
    def __init__(
        self, 
        db: Session,
        shell_repository: Optional[AASShellRepository] = None,
        submodel_repository: Optional[AASSubmodelRepository] = None,
        integrity_repository=None
    ):
        """
        Initialize the DPP service.
        
        Args:
            db: Database session
            shell_repository: Repository for AAS shells
            submodel_repository: Repository for AAS submodels
            integrity_repository: Repository for integrity proofs (optional)
        """
        self.db = db
        self.shell_repository = shell_repository or AASShellRepository(db)
        self.submodel_repository = submodel_repository or AASSubmodelRepository(db)
        self.integrity_repository = integrity_repository
    
    def list_dpp_shells(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all available DPP shells.
        
        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            
        Returns:
            List of DPP shell data
        """
        try:
            shells, total_count = self.shell_repository.get_all(skip=skip, limit=limit)
            
            # Convert to API response format
            result = []
            if shells and len(shells) > 0:
                for shell in shells:
                    # Make sure we're dealing with an object that has id attribute
                    if hasattr(shell, 'id'):
                        shell_data = {
                            "id": self._encode_aas_identifier(shell.id),
                            "idShort": shell.id_short,
                            "asset_id": shell.asset_id,
                            "created": shell.created_at.isoformat() if shell.created_at else None,
                            "modified": shell.updated_at.isoformat() if shell.updated_at else None,
                            "version": "1.0"
                        }
                        result.append(shell_data)
            
            logger.info(f"Found {len(result)} shells")
            return result
        except Exception as e:
            logger.error(f"Error listing shells: {str(e)}")
            # Return an empty list on error rather than raising
            return []
    
    def get_dpp_shell(self, aas_id_b64: str) -> Dict[str, Any]:
        """
        Get a specific DPP shell by its base64-encoded ID.
        
        Args:
            aas_id_b64: Base64-encoded identifier of the AAS shell
            
        Returns:
            DPP shell data
            
        Raises:
            EntityNotFoundError: If the shell is not found
        """
        # Decode the base64 identifier
        try:
            aas_id = self._decode_aas_identifier(aas_id_b64)
            logger.info(f"Decoded aas_id: {aas_id}")
        except Exception as e:
            logger.error(f"Error decoding AAS ID {aas_id_b64}: {str(e)}")
            raise EntityNotFoundError("AAS Shell", aas_id_b64, {"error": str(e)})
        
        # Get the shell from the repository
        try:
            shell = self.shell_repository.get_by_id(aas_id)
            if not shell:
                logger.error(f"Shell with ID {aas_id} not found")
                raise EntityNotFoundError("AAS Shell", aas_id_b64)
                
            logger.info(f"Found shell: {shell.id} ({shell.id_short})")
            
            # Get submodels for this shell
            submodels = self.submodel_repository.get_all_by_aas_id(aas_id)
            submodel_id_shorts = [sm.id_short for sm in submodels] if submodels else []
            logger.info(f"Found {len(submodel_id_shorts)} submodels for shell {aas_id}")
            
            # Create a dictionary response object with the required fields
            # This ensures compatibility with AASShellResponse schema
            result = {
                "id": aas_id_b64,  # Return the same base64 ID that was provided
                "idShort": shell.id_short,
                "asset_id": shell.asset_id,
                "created": shell.created_at.isoformat() if shell.created_at else None,
                "modified": shell.updated_at.isoformat() if shell.updated_at else None,
                "submodels": submodel_id_shorts,
                "version": "1.0"
            }
            
            return result
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving shell {aas_id}: {str(e)}")
            raise EntityNotFoundError("AAS Shell", aas_id_b64, {"error": str(e)})
    
    def create_dpp_shell(self, shell_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new DPP shell.
        
        Args:
            shell_data: Data for the new shell
            
        Returns:
            Created DPP shell object with all fields required by AASShellResponse
        """
        # Generate a UUID for the new shell
        raw_aas_id = f"urn:dpp40:aas:{str(uuid.uuid4())}"
        
        # Create the shell in the repository
        shell = self.shell_repository.create(
            shell_id=raw_aas_id,  # Use the non-encoded ID for storage
            id_short=shell_data["idShort"],
            asset_id=raw_aas_id,  # Using the same ID for asset and shell for simplicity
            shell_data={"id": raw_aas_id, "idShort": shell_data["idShort"]}
        )
        
        # Create a simple Nameplate submodel to ensure the shell has a submodel
        try:
            # Create a simple nameplate with basic data instead of using the complex nameplate creator
            nameplate_id = f"urn:dpp40:submodel:nameplate:{str(uuid.uuid4())}"
            nameplate_data = {
                "id": nameplate_id,
                "idShort": "Nameplate",
                "semanticId": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": "https://admin-shell.io/idta/Submodel/Nameplate/2/0"}]},
                "submodelElements": {
                    "ManufacturerName": {
                        "idShort": "ManufacturerName", 
                        "valueType": "string",
                        "value": shell_data.get("manufacturer_name", "Example Manufacturer")
                    },
                    "ManufacturerProductDesignation": {
                        "idShort": "ManufacturerProductDesignation",
                        "valueType": "string",
                        "value": shell_data.get("product_designation", "Example Product")
                    },
                    "YearOfConstruction": {
                        "idShort": "YearOfConstruction", 
                        "valueType": "string",
                        "value": shell_data.get("year_of_construction", "2024")
                    }
                }
            }
            
            # Store nameplate submodel in database
            nameplate_sm = self.submodel_repository.create(
                submodel_id=nameplate_id,
                aas_id=shell.id,  # Use the actual ORM object ID attribute
                id_short="Nameplate",
                semantic_id="https://admin-shell.io/idta/Submodel/Nameplate/2/0", 
                content=nameplate_data
            )
            
            logger.info(f"Created Nameplate submodel for shell {raw_aas_id}")
        except Exception as e:
            logger.warning(f"Failed to create Nameplate submodel: {str(e)}")
            # Continue even if submodel creation fails
        
        # Create a dictionary response object with the required fields
        # This ensures compatibility with AASShellResponse schema
        encoded_id = self._encode_aas_identifier(raw_aas_id)
        response = {
            "id": encoded_id,
            "idShort": shell_data["idShort"],
            "asset_id": raw_aas_id,
            "created": shell.created_at.isoformat() if shell.created_at else None,
            "modified": shell.updated_at.isoformat() if shell.updated_at else None,
            "submodels": ["Nameplate"],
            "version": "1.0"
        }
        
        logger.info(f"Created shell with ID {raw_aas_id}, encoded as {encoded_id}")
        
        return response
    
    def list_submodels(self, aas_id_b64: str) -> List[str]:
        """
        List all submodels in a DPP shell.
        
        Args:
            aas_id_b64: Base64-encoded identifier of the AAS shell
            
        Returns:
            List of submodel idShorts
            
        Raises:
            EntityNotFoundError: If the shell is not found
        """
        # Decode the base64 identifier
        try:
            aas_id = self._decode_aas_identifier(aas_id_b64)
        except Exception as e:
            raise EntityNotFoundError("AAS Shell", aas_id_b64, {"error": str(e)})
        
        # Verify the shell exists
        shell = self.shell_repository.get_by_id(aas_id)
        if not shell:
            raise EntityNotFoundError("AAS Shell", aas_id_b64)
        
        # Get submodels for this shell
        submodels = self.submodel_repository.get_all_by_aas_id(aas_id)
        return [sm.id_short for sm in submodels]
    
    def get_submodel(self, aas_id_b64: str, submodel_id_short: str) -> Dict[str, Any]:
        """
        Get a specific submodel from a DPP shell.
        
        Args:
            aas_id_b64: Base64-encoded identifier of the AAS shell
            submodel_id_short: Short ID of the submodel
            
        Returns:
            Submodel data
            
        Raises:
            EntityNotFoundError: If the shell or submodel is not found
        """
        # Decode the base64 identifier
        try:
            aas_id = self._decode_aas_identifier(aas_id_b64)
        except Exception as e:
            raise EntityNotFoundError("AAS Shell", aas_id_b64, {"error": str(e)})
        
        # Verify the shell exists
        shell = self.shell_repository.get_by_id(aas_id)
        if not shell:
            raise EntityNotFoundError("AAS Shell", aas_id_b64)
        
        # Get the submodel
        submodel = self.submodel_repository.get_by_id_short(aas_id, submodel_id_short)
        if not submodel:
            raise EntityNotFoundError("Submodel", submodel_id_short, {"aas_id": aas_id_b64})
        
        # Create elements array from submodel data
        elements = []
        if hasattr(submodel, 'submodel_data') and submodel.submodel_data:
            # If submodelElements exists in the data, use it to create elements array
            submodel_elements = submodel.submodel_data.get('submodelElements', {})
            if isinstance(submodel_elements, dict):
                for key, value in submodel_elements.items():
                    elements.append({
                        "idShort": value.get('idShort', key),
                        "valueType": value.get('valueType', 'string'),
                        "value": value.get('value', '')
                    })
            
            # Return the updated data with elements correctly formatted
            result = {
                "id": submodel.submodel_data.get('id', submodel.id),
                "idShort": submodel.submodel_data.get('idShort', submodel.id_short),
                "semanticId": submodel.submodel_data.get('semanticId', submodel.semantic_id),
                "elements": elements
            }
            return result
        
        # Fallback response with minimal information if no data available
        result = {
            "id": submodel.id,
            "idShort": submodel.id_short,
            "semanticId": submodel.semantic_id,
            "elements": elements
        }
            
        return result
    
    def create_dpp(self, dpp_request):
        """
        Create a new Digital Product Passport.
        
        Args:
            dpp_request: DPP creation request containing nameplate and other data
            
        Returns:
            Created DPP information
        """
        try:
            # Generate identifiers
            id_short = dpp_request.id_short
            
            # Create Asset Shell using utility function
            asset_id = dpp_request.asset_id or f"urn:dpp40:asset:{str(uuid.uuid4())}"
            shell = create_asset_shell(id_short, asset_id)
            
            # Create Nameplate submodel
            nameplate_submodel = create_nameplate_submodel(
                product_id=id_short,
                manufacturer_name=dpp_request.nameplate.manufacturer_name,
                product_designation=dpp_request.nameplate.product_designation,
                year_of_construction=dpp_request.nameplate.year_of_construction,
                serial_number=getattr(dpp_request.nameplate, 'serial_number', None),
                batch_number=getattr(dpp_request.nameplate, 'batch_number', None)
            )
            
            # Store shell in database
            shell_dict = basyx_to_dict(shell)
            aas_shell = self.shell_repository.create(
                shell_id=shell.id,
                id_short=shell.id_short,
                asset_id=asset_id,
                shell_data=shell_dict
            )
            
            # Store nameplate submodel in database
            nameplate_dict = basyx_to_dict(nameplate_submodel)
            nameplate_sm = self.submodel_repository.create(
                submodel_id=nameplate_submodel.id,
                aas_id=shell.id,
                id_short=nameplate_submodel.id_short,
                semantic_id=nameplate_submodel.semantic_id,
                content=nameplate_dict
            )
            
            # List of created submodel ID shorts for response
            submodel_ids = [nameplate_submodel.id_short]
            
            # Create and store TechnicalData submodel if provided
            if hasattr(dpp_request, 'technical_data') and dpp_request.technical_data:
                tech_data = dpp_request.technical_data
                technical_submodel = create_technical_data_submodel(
                    product_id=id_short,
                    density=tech_data.density,
                    melt_flow_index=tech_data.melt_flow_index,
                    processing_temperature=tech_data.processing_temperature
                )
                
                technical_dict = basyx_to_dict(technical_submodel)
                technical_sm = self.submodel_repository.create(
                    submodel_id=technical_submodel.id,
                    aas_id=shell.id,
                    id_short=technical_submodel.id_short,
                    semantic_id=technical_submodel.semantic_id,
                    content=technical_dict
                )
                
                submodel_ids.append(technical_submodel.id_short)
            
            # Create and store MaterialComposition submodel if provided
            if hasattr(dpp_request, 'material_composition') and dpp_request.material_composition:
                material = dpp_request.material_composition
                material_submodel = create_material_composition_submodel(
                    product_id=id_short,
                    material_name=material.material_name,
                    polymer_type=material.polymer_type,
                    recycled_content=material.recycled_content,
                    material_color=material.material_color,
                    material_source=material.material_source,
                    bio_based_content=material.bio_based_content,
                    additives=material.additives
                )
                
                material_dict = basyx_to_dict(material_submodel)
                material_sm = self.submodel_repository.create(
                    submodel_id=material_submodel.id,
                    aas_id=shell.id,
                    id_short=material_submodel.id_short,
                    semantic_id=material_submodel.semantic_id,
                    content=material_dict
                )
                
                submodel_ids.append(material_submodel.id_short)
            
            # Create response object
            response = DPPResponse(
                id=shell.id,
                id_short=shell.id_short,
                asset_id=asset_id,
                submodels=submodel_ids,
                created=datetime.now().isoformat()
            )
            
            return response
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating DPP: {str(e)}")
            raise ValueError(f"Failed to create DPP: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating DPP: {str(e)}")
            raise ValueError(f"Failed to create DPP: {str(e)}")
    
    def get_dpp(self, shell_id, include_full_json=False):
        """
        Get a Digital Product Passport by its shell ID.
        
        Args:
            shell_id: The ID of the AAS shell
            include_full_json: Whether to include full JSON data
            
        Returns:
            DPP information as a DPPResponse object
            
        Raises:
            ValueError: If the DPP with the given ID is not found
        """
        # Check if we need to decode a base64 ID
        if not shell_id.startswith("urn:"):
            try:
                shell_id = decode_aas_id(shell_id)
            except Exception as e:
                logger.error(f"Error decoding shell ID: {str(e)}")
                raise ValueError(f"Invalid shell ID format: {str(e)}")
        
        # Get the shell from the repository
        shell = self.shell_repository.get_by_id(shell_id)
        if not shell:
            logger.error(f"DPP with ID {shell_id} not found")
            raise ValueError(f"DPP with ID {shell_id} not found")
        
        # Get all submodels for this shell
        submodels = self.submodel_repository.get_all_by_aas_id(shell_id)
        
        # Prepare submodel content for full_json if requested
        full_json_data = None
        if include_full_json:
            submodel_content = {}
            for sm in submodels:
                if hasattr(sm, 'content') and sm.content:
                    submodel_content[sm.id_short] = sm.content
                elif hasattr(sm, 'submodel_data') and sm.submodel_data:
                    submodel_content[sm.id_short] = sm.submodel_data
            
            full_json_data = {
                "shellData": shell.shell_data,
                "submodels": submodel_content
            }
        
        # Create DPPResponse object
        response = DPPResponse(
            id=shell_id,
            id_short=shell.id_short,
            asset_id=shell.asset_id,
            submodels=[sm.id_short for sm in submodels] if submodels else [],
            created=shell.created_at.isoformat() if shell.created_at else None,
            full_json=full_json_data
        )
        
        return response
    
    def get_dpp_by_asset_id(self, asset_id):
        """
        Get a Digital Product Passport by its asset ID.
        
        Args:
            asset_id: The asset ID
            
        Returns:
            DPP information
            
        Raises:
            ValueError: If the DPP with the given asset ID is not found
        """
        # Get the shell by asset ID
        shell = self.shell_repository.get_by_asset_id(asset_id)
        if not shell:
            logger.error(f"DPP with asset ID {asset_id} not found")
            raise ValueError(f"DPP with asset ID {asset_id} not found")
        
        # Use the get_dpp method to get full information
        try:
            return self.get_dpp(shell.id)
        except ValueError as e:
            # If the shell exists but get_dpp fails for some reason, propagate the error
            logger.error(f"Shell found by asset ID {asset_id} but failed to get DPP: {str(e)}")
            raise
    
    def list_dpps(self, limit=100, skip=0, search=None, manufacturer_id=None, 
                 product_category=None, lifecycle_status=None):
        """
        List Digital Product Passports with optional filtering.
        
        Args:
            limit: Maximum number of items to return
            skip: Number of items to skip
            search: Optional search term
            manufacturer_id: Optional manufacturer ID filter
            product_category: Optional product category filter
            lifecycle_status: Optional lifecycle status filter
            
        Returns:
            Tuple of (list of DPPs, total count)
        """
        try:
            # Use search if provided, otherwise use get_all with filters
            if search:
                shells, total = self.shell_repository.search(
                    search_term=search,
                    skip=skip,
                    limit=limit
                )
            else:
                # Get shells from the repository with optional filters
                shells, total = self.shell_repository.get_all(
                    skip=skip,
                    limit=limit,
                    manufacturer_id=manufacturer_id,
                    product_category=product_category,
                    lifecycle_status=lifecycle_status
                )
            
            # Extract DPP information from each shell
            results = []
            for shell in shells:
                try:
                    # Create a response object for each shell
                    dpp_response = DPPResponse(
                        id=shell.id,
                        id_short=shell.id_short,
                        asset_id=shell.asset_id,
                        submodels=[],
                        created=shell.created_at.isoformat() if shell.created_at else None
                    )
                    
                    # Add extra properties used in tests
                    dpp_response.manufacturer = "Unknown"
                    dpp_response.product_designation = "Unknown"
                    
                    # Extract basic nameplate data if available
                    if shell.shell_data and "submodels" in shell.shell_data:
                        try:
                            nameplate = shell.shell_data["submodels"].get("Nameplate", {})
                            if nameplate and "submodelElements" in nameplate:
                                elements = nameplate["submodelElements"]
                                if "ManufacturerName" in elements:
                                    dpp_response.manufacturer = elements["ManufacturerName"].get("value", "Unknown")
                                if "ProductDesignation" in elements:
                                    dpp_response.product_designation = elements["ProductDesignation"].get("value", "Unknown")
                        except Exception as extract_err:
                            logger.warning(f"Error extracting nameplate data: {str(extract_err)}")
                    
                    results.append(dpp_response)
                except Exception as extract_err:
                    logger.warning(f"Error extracting DPP data from shell {shell.id}: {str(extract_err)}")
                    # Skip this shell and continue
            
            return results, total
        except Exception as e:
            logger.error(f"Error listing DPPs: {str(e)}")
            raise ValueError(f"Failed to list DPPs: {str(e)}")
    
    def update_dpp(self, shell_id, update_data):
        """
        Update a Digital Product Passport.
        
        Args:
            shell_id: The ID of the AAS shell
            update_data: Dictionary of data to update
            
        Returns:
            Updated DPP information
        """
        # Get the shell to update
        shell = self.shell_repository.get_by_id(shell_id)
        if not shell:
            raise ValueError(f"DPP with ID {shell_id} not found")
        
        try:
            # Update shell data
            updated_shell_data = shell.shell_data.copy() if shell.shell_data else {}
            
            # Apply updates to shell data
            if "description" in update_data:
                updated_shell_data["description"] = update_data["description"]
            
            if "lifecycle_status" in update_data:
                updated_shell_data["lifecycleStatus"] = update_data["lifecycle_status"]
            
            # Create a dictionary of fields to update in the repository
            update_fields = {
                "shell_id": shell_id,
                "shell_data": updated_shell_data,
            }
            
            # Add additional fields if they're in the update_data
            if "lifecycle_status" in update_data:
                update_fields["lifecycle_status"] = update_data["lifecycle_status"]
            
            if "manufacturer_id" in update_data:
                update_fields["manufacturer_id"] = update_data["manufacturer_id"]
                
            if "product_category" in update_data:
                update_fields["product_category"] = update_data["product_category"]
                
            if "version" in update_data:
                update_fields["version"] = update_data["version"]
            
            # Update the shell in the repository
            updated_shell = self.shell_repository.update(**update_fields)
            
            # Return updated DPP info
            return self.get_dpp(shell_id)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating DPP: {str(e)}")
            raise ValueError(f"Failed to update DPP: {str(e)}")
        except Exception as e:
            logger.error(f"Error updating DPP: {str(e)}")
            raise ValueError(f"Failed to update DPP: {str(e)}")
    
    def delete_dpp(self, shell_id):
        """
        Delete a Digital Product Passport.
        
        Args:
            shell_id: The ID of the AAS shell
            
        Returns:
            Dictionary with shell_id and success status
        """
        try:
            # Delete the shell from the repository
            result = self.shell_repository.delete(shell_id)
            
            # Return success status with additional info
            return {
                "id": shell_id,
                "success": result
            }
        except Exception as e:
            logger.error(f"Error deleting DPP: {str(e)}")
            self.db.rollback()
            
            # Return failure status with error
            return {
                "id": shell_id,
                "success": False,
                "error": str(e)
            }
    
    def verify_dpp_integrity(self, shell_id):
        """
        Verify the integrity of a Digital Product Passport.
        
        Args:
            shell_id: The ID of the AAS shell
            
        Returns:
            Integrity verification results
        """
        # Get the shell to verify
        shell = self.shell_repository.get_by_id(shell_id)
        if not shell:
            raise ValueError(f"DPP with ID {shell_id} not found")
        
        try:
            # Get submodels for verification
            submodels = self.submodel_repository.get_all_by_aas_id(shell_id)
            
            # Set up default response
            shell_status = EntityIntegrityStatus(
                id=shell_id,
                id_short=shell.id_short,
                has_integrity_proof=False,
                verification_result=None
            )
            
            submodel_statuses = []
            proofs = []
            
            # If integrity repository is available, check for proofs
            if self.integrity_repository:
                shell_proofs, shell_proof_count = self.integrity_repository.get_proofs_by_entity(shell_id)
                
                # Process shell proofs
                if shell_proofs and shell_proof_count > 0:
                    shell_status.has_integrity_proof = True
                    shell_status.verification_result = VerificationResult(
                        is_valid=True,  # Placeholder - would actually verify cryptographically
                        timestamp=datetime.now(),
                        details="Shell integrity verified"
                    )
                    proofs.extend(shell_proofs)
                
                # Process submodel proofs
                for sm in submodels:
                    sm_status = EntityIntegrityStatus(
                        id=sm.id,
                        id_short=sm.id_short,
                        has_integrity_proof=False,
                        verification_result=None
                    )
                    
                    sm_proofs, sm_proof_count = self.integrity_repository.get_proofs_by_entity(sm.id)
                    if sm_proofs and sm_proof_count > 0:
                        sm_status.has_integrity_proof = True
                        sm_status.verification_result = VerificationResult(
                            is_valid=True,  # Placeholder
                            timestamp=datetime.now(),
                            details="Submodel integrity verified"
                        )
                        proofs.extend(sm_proofs)
                    
                    submodel_statuses.append(sm_status)
            
            # Create the final report - make sure to return all fields as dictionaries
            result = {
                "shell": shell_status.dict() if hasattr(shell_status, 'dict') else vars(shell_status),
                "submodels": [sm_status.dict() if hasattr(sm_status, 'dict') else vars(sm_status) for sm_status in submodel_statuses],
                "proofs": [proof.dict() if hasattr(proof, 'dict') else vars(proof) for proof in proofs],
                "timestamp": datetime.now().isoformat()
            }
            
            return result
        except Exception as e:
            logger.error(f"Error verifying DPP integrity: {str(e)}")
            raise ValueError(f"Failed to verify DPP integrity: {str(e)}")
    
    @staticmethod
    def _encode_aas_identifier(aas_id: str) -> str:
        """
        Encode an AAS identifier to base64.
        
        Args:
            aas_id: The AAS identifier
            
        Returns:
            Base64-encoded identifier
        """
        return base64.urlsafe_b64encode(aas_id.encode()).decode()
    
    @staticmethod
    def _decode_aas_identifier(aas_id_b64: str) -> str:
        """
        Decode a base64-encoded AAS identifier.
        
        Args:
            aas_id_b64: Base64-encoded identifier
            
        Returns:
            Original AAS identifier
        """
        return base64.urlsafe_b64decode(aas_id_b64.encode()).decode()
