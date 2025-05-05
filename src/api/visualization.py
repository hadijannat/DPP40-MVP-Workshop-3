"""
Visualization endpoints for DPP40 MVP.

This module provides endpoints for visualizing DPP data in various formats
including lifecycle visualization, value chain visualization, and digital twin visualization.
"""
from typing import Dict, List, Any, Optional
import logging
import networkx as nx
import matplotlib.pyplot as plt
import io
import base64
from pathlib import Path
import os

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, status
from fastapi.responses import JSONResponse, FileResponse, Response

from ..api import dependencies
from ..db.session import get_db
from ..services.dpp_service import DPPService
from ..utils.errors import EntityNotFoundError
from ..utils.aas_utils import decode_aas_id
from sqlalchemy.orm import Session

# Setup logger
logger = logging.getLogger(__name__)

# Create router with appropriate prefix and tags
router = APIRouter(
    prefix="/visualization",
    tags=["Visualization"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        500: {"description": "Internal server error"}
    }
)

# Ensure visualization directory exists
VISUALIZATION_DIR = Path("/tmp/dpp_visualizations")
VISUALIZATION_DIR.mkdir(exist_ok=True)

@router.get(
    "/lifecycle/{aas_id_b64}",
    summary="Get lifecycle visualization for a DPP",
    description="Returns a visualization of the product lifecycle stages"
)
async def get_lifecycle_visualization(
    aas_id_b64: str = PathParam(..., description="Base64-encoded identifier of the AAS Shell"),
    format: str = Query("png", description="Output format (png, svg, json)"),
    db: Session = Depends(get_db),
    dpp_service: DPPService = Depends(dependencies.get_dpp_service)
):
    """
    Generate a lifecycle visualization for a Digital Product Passport.
    
    Args:
        aas_id_b64: Base64-encoded identifier of the AAS Shell
        format: Output format (png, svg, json)
        db: Database session
        dpp_service: DPP service
        
    Returns:
        Visualization in the requested format
    """
    try:
        # Decode the base64 AAS ID
        try:
            aas_id = decode_aas_id(aas_id_b64)
            logger.debug(f"Decoded AAS ID: {aas_id}")
        except Exception as e:
            logger.error(f"Error decoding AAS ID {aas_id_b64}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid AAS ID format: {aas_id_b64}"
            )
        
        # Get the DPP shell
        shell = dpp_service.get_dpp_shell(aas_id_b64)
        if not shell:
            raise EntityNotFoundError("AAS Shell", aas_id_b64)
        
        # Create a simple lifecycle graph
        G = nx.DiGraph()
        
        # Add nodes for lifecycle stages
        stages = ["Raw Materials", "Manufacturing", "Distribution", "Use", "End of Life"]
        for i, stage in enumerate(stages):
            G.add_node(stage, pos=(i, 0))
        
        # Add edges between stages
        for i in range(len(stages) - 1):
            G.add_edge(stages[i], stages[i + 1])
        
        # Add recycling edge
        G.add_edge(stages[-1], stages[0], color='green', style='dashed')
        
        if format.lower() == "json":
            # Return graph as JSON
            nodes = [{"id": node, "stage": i} for i, node in enumerate(G.nodes())]
            edges = [{"source": u, "target": v, "recycling": u == stages[-1] and v == stages[0]} 
                    for u, v in G.edges()]
            
            return {"nodes": nodes, "edges": edges, "product_id": shell["idShort"]}
        
        # Generate visualization
        plt.figure(figsize=(10, 4))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=1500, 
                font_size=10, font_weight='bold', arrows=True)
        
        # Add title
        plt.title(f"Lifecycle Visualization for {shell['idShort']}")
        
        # Save to file
        filename = f"{VISUALIZATION_DIR}/lifecycle_{aas_id_b64}.{format}"
        plt.savefig(filename, format=format, bbox_inches='tight')
        plt.close()
        
        # Return file
        return FileResponse(
            filename,
            media_type=f"image/{format}",
            filename=f"lifecycle_{shell['idShort']}.{format}"
        )
        
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error generating lifecycle visualization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating visualization: {str(e)}"
        )

@router.get(
    "/value-chain/{aas_id_b64}",
    summary="Get value chain visualization for a DPP",
    description="Returns a visualization of the product value chain"
)
async def get_value_chain_visualization(
    aas_id_b64: str = PathParam(..., description="Base64-encoded identifier of the AAS Shell"),
    format: str = Query("png", description="Output format (png, svg, json)"),
    db: Session = Depends(get_db),
    dpp_service: DPPService = Depends(dependencies.get_dpp_service)
):
    """
    Generate a value chain visualization for a Digital Product Passport.
    
    Args:
        aas_id_b64: Base64-encoded identifier of the AAS Shell
        format: Output format (png, svg, json)
        db: Database session
        dpp_service: DPP service
        
    Returns:
        Visualization in the requested format
    """
    try:
        # Decode the base64 AAS ID
        try:
            aas_id = decode_aas_id(aas_id_b64)
            logger.debug(f"Decoded AAS ID: {aas_id}")
        except Exception as e:
            logger.error(f"Error decoding AAS ID {aas_id_b64}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid AAS ID format: {aas_id_b64}"
            )
        
        # Get the DPP shell
        shell = dpp_service.get_dpp_shell(aas_id_b64)
        if not shell:
            raise EntityNotFoundError("AAS Shell", aas_id_b64)
        
        # Create a simple value chain graph
        G = nx.DiGraph()
        
        # Add nodes for value chain actors
        actors = ["Raw Material Supplier", "Manufacturer", "Distributor", "Retailer", "Consumer"]
        for i, actor in enumerate(actors):
            G.add_node(actor, pos=(i, 0))
        
        # Add edges between actors
        for i in range(len(actors) - 1):
            G.add_edge(actors[i], actors[i + 1])
        
        if format.lower() == "json":
            # Return graph as JSON
            nodes = [{"id": node, "type": node} for node in G.nodes()]
            edges = [{"source": u, "target": v} for u, v in G.edges()]
            
            return {"nodes": nodes, "edges": edges, "product_id": shell["idShort"]}
        
        # Generate visualization
        plt.figure(figsize=(12, 4))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='lightgreen', node_size=1500, 
                font_size=10, font_weight='bold', arrows=True)
        
        # Add title
        plt.title(f"Value Chain Visualization for {shell['idShort']}")
        
        # Save to file
        filename = f"{VISUALIZATION_DIR}/value_chain_{aas_id_b64}.{format}"
        plt.savefig(filename, format=format, bbox_inches='tight')
        plt.close()
        
        # Return file
        return FileResponse(
            filename,
            media_type=f"image/{format}",
            filename=f"value_chain_{shell['idShort']}.{format}"
        )
        
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error generating value chain visualization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating visualization: {str(e)}"
        )

@router.get(
    "/digital-twin/{aas_id_b64}",
    summary="Get digital twin visualization for a DPP",
    description="Returns a visualization of the digital twin structure"
)
async def get_digital_twin_visualization(
    aas_id_b64: str = PathParam(..., description="Base64-encoded identifier of the AAS Shell"),
    format: str = Query("png", description="Output format (png, svg, json)"),
    db: Session = Depends(get_db),
    dpp_service: DPPService = Depends(dependencies.get_dpp_service)
):
    """
    Generate a digital twin visualization for a Digital Product Passport.
    
    Args:
        aas_id_b64: Base64-encoded identifier of the AAS Shell
        format: Output format (png, svg, json)
        db: Database session
        dpp_service: DPP service
        
    Returns:
        Visualization in the requested format
    """
    try:
        # Decode the base64 AAS ID
        try:
            aas_id = decode_aas_id(aas_id_b64)
            logger.debug(f"Decoded AAS ID: {aas_id}")
        except Exception as e:
            logger.error(f"Error decoding AAS ID {aas_id_b64}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid AAS ID format: {aas_id_b64}"
            )
        
        # Get the DPP shell
        shell = dpp_service.get_dpp_shell(aas_id_b64)
        if not shell:
            raise EntityNotFoundError("AAS Shell", aas_id_b64)
        
        # Get submodels
        submodels = shell.get("submodels", [])
        
        # Create a digital twin graph
        G = nx.DiGraph()
        
        # Add central node for the AAS
        G.add_node(shell["idShort"], type="AAS")
        
        # Add nodes for submodels
        for submodel in submodels:
            G.add_node(submodel, type="Submodel")
            G.add_edge(shell["idShort"], submodel)
        
        if format.lower() == "json":
            # Return graph as JSON
            nodes = [{"id": node, "type": G.nodes[node]["type"]} for node in G.nodes()]
            edges = [{"source": u, "target": v} for u, v in G.edges()]
            
            return {"nodes": nodes, "edges": edges, "product_id": shell["idShort"]}
        
        # Generate visualization
        plt.figure(figsize=(8, 6))
        pos = nx.spring_layout(G)
        
        # Draw nodes with different colors based on type
        aas_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "AAS"]
        submodel_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "Submodel"]
        
        nx.draw_networkx_nodes(G, pos, nodelist=aas_nodes, node_color='red', node_size=1500)
        nx.draw_networkx_nodes(G, pos, nodelist=submodel_nodes, node_color='blue', node_size=1000)
        nx.draw_networkx_edges(G, pos, arrows=True)
        nx.draw_networkx_labels(G, pos, font_weight='bold')
        
        # Add title
        plt.title(f"Digital Twin Structure for {shell['idShort']}")
        
        # Save to file
        filename = f"{VISUALIZATION_DIR}/digital_twin_{aas_id_b64}.{format}"
        plt.savefig(filename, format=format, bbox_inches='tight')
        plt.close()
        
        # Return file
        return FileResponse(
            filename,
            media_type=f"image/{format}",
            filename=f"digital_twin_{shell['idShort']}.{format}"
        )
        
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error generating digital twin visualization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating visualization: {str(e)}"
        )

@router.get(
    "/qrcode/{aas_id_b64}",
    summary="Get QR code for a DPP",
    description="Returns a QR code for accessing the DPP"
)
async def get_qrcode(
    aas_id_b64: str = PathParam(..., description="Base64-encoded identifier of the AAS Shell"),
    size: int = Query(200, description="QR code size in pixels"),
    db: Session = Depends(get_db),
    dpp_service: DPPService = Depends(dependencies.get_dpp_service)
):
    """
    Generate a QR code for a Digital Product Passport.
    
    Args:
        aas_id_b64: Base64-encoded identifier of the AAS Shell
        size: QR code size in pixels
        db: Database session
        dpp_service: DPP service
        
    Returns:
        QR code image
    """
    try:
        # Verify the DPP exists
        shell = dpp_service.get_dpp_shell(aas_id_b64)
        if not shell:
            raise EntityNotFoundError("AAS Shell", aas_id_b64)
        
        # Import qrcode here to avoid dependency issues
        import qrcode
        from qrcode.image.pure import PymagingImage
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Add data - URL to access the DPP
        qr.add_data(f"/dpp-detail.html?id={aas_id_b64}")
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to file
        filename = f"{VISUALIZATION_DIR}/qrcode_{aas_id_b64}.png"
        img.save(filename)
        
        # Return file
        return FileResponse(
            filename,
            media_type="image/png",
            filename=f"qrcode_{shell['idShort']}.png"
        )
        
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error generating QR code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating QR code: {str(e)}"
        )

@router.get(
    "/submodel/{aas_id_b64}/{submodel_id_short}",
    summary="Get visualization for a specific submodel",
    description="Returns a visualization of a specific submodel"
)
async def get_submodel_visualization(
    aas_id_b64: str = PathParam(..., description="Base64-encoded identifier of the AAS Shell"),
    submodel_id_short: str = PathParam(..., description="Short ID of the submodel"),
    format: str = Query("png", description="Output format (png, svg, json)"),
    db: Session = Depends(get_db),
    dpp_service: DPPService = Depends(dependencies.get_dpp_service)
):
    """
    Generate a visualization for a specific submodel.
    
    Args:
        aas_id_b64: Base64-encoded identifier of the AAS Shell
        submodel_id_short: Short ID of the submodel
        format: Output format (png, svg, json)
        db: Database session
        dpp_service: DPP service
        
    Returns:
        Visualization in the requested format
    """
    try:
        # Get the submodel
        submodel = dpp_service.get_submodel(aas_id_b64, submodel_id_short)
        if not submodel:
            raise EntityNotFoundError("Submodel", submodel_id_short, {"aas_id": aas_id_b64})
        
        # Get elements
        elements = submodel.get("elements", [])
        
        if format.lower() == "json":
            # Return elements as JSON
            return {
                "id": submodel.get("id"),
                "idShort": submodel.get("idShort"),
                "elements": elements
            }
        
        # Create a graph for the submodel
        G = nx.DiGraph()
        
        # Add central node for the submodel
        G.add_node(submodel_id_short, type="Submodel")
        
        # Add nodes for elements
        for element in elements:
            element_id = element.get("idShort", "Unknown")
            G.add_node(element_id, type="Element", value=element.get("value", ""))
            G.add_edge(submodel_id_short, element_id)
        
        # Generate visualization
        plt.figure(figsize=(10, 8))
        pos = nx.spring_layout(G)
        
        # Draw nodes with different colors based on type
        submodel_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "Submodel"]
        element_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "Element"]
        
        nx.draw_networkx_nodes(G, pos, nodelist=submodel_nodes, node_color='orange', node_size=1500)
        nx.draw_networkx_nodes(G, pos, nodelist=element_nodes, node_color='lightblue', node_size=1000)
        nx.draw_networkx_edges(G, pos, arrows=True)
        nx.draw_networkx_labels(G, pos, font_weight='bold')
        
        # Add title
        plt.title(f"Submodel: {submodel_id_short}")
        
        # Save to file
        filename = f"{VISUALIZATION_DIR}/submodel_{aas_id_b64}_{submodel_id_short}.{format}"
        plt.savefig(filename, format=format, bbox_inches='tight')
        plt.close()
        
        # Return file
        return FileResponse(
            filename,
            media_type=f"image/{format}",
            filename=f"submodel_{submodel_id_short}.{format}"
        )
        
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error generating submodel visualization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating visualization: {str(e)}"
        )
