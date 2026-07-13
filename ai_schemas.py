from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class Conflict(BaseModel):
    path: List[str] = Field(description="The JSON path to the field, e.g. ['summary', 'abstract']")
    incoming: str = Field(description="The new text found in the document")
    devised: str = Field(description="The AI's suggested merged text")
    contradiction: Optional[str] = Field(None, description="A concise warning if the incoming text contradicts the existing text, or null")

class DataCustodian(BaseModel):
    name: Optional[str] = None
    identifier: Optional[str] = None
    description: Optional[str] = None

class Summary(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    dataCustodian: Optional[DataCustodian] = None
    populationSize: Optional[int] = None
    keywords: Optional[List[str]] = None
    datasetAliases: Optional[List[str]] = None
    contactPoint: Optional[str] = None
    doiName: Optional[str] = None

class Documentation(BaseModel):
    associatedMedia: Optional[List[str]] = None
    inPipeline: Optional[str] = None
    description: Optional[str] = None

class DatasetFilter(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None
    category: Optional[str] = None
    primaryGroup: Optional[str] = None
    description: Optional[str] = None

class StructuralColumn(BaseModel):
    name: Optional[str] = None
    dataType: Optional[str] = None
    description: Optional[str] = None
    sensitive: Optional[bool] = None
    values: Optional[List[Any]] = None

class StructuralTable(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    size: Optional[int] = None
    columns: Optional[List[StructuralColumn]] = None

class StructuralMetadata(BaseModel):
    tables: Optional[List[StructuralTable]] = None

class OtherDataType(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None

class Coverage(BaseModel):
    typicalAgeRangeMin: Optional[int] = None
    typicalAgeRangeMax: Optional[int] = None
    datasetCompleteness: Optional[str] = None

class EnrichmentAndLinkage(BaseModel):
    publicationUsingDataset: Optional[List[str]] = None

class Access(BaseModel):
    accessRights: Optional[str] = None
    accessServiceCategory: Optional[str] = None

class Accessibility(BaseModel):
    access: Optional[Access] = None

class Dataset(BaseModel):
    summary: Optional[Summary] = None
    documentation: Optional[Documentation] = None
    datasetFilters: Optional[List[DatasetFilter]] = None
    structuralMetadata: Optional[StructuralMetadata] = None
    otherDataTypes: Optional[List[OtherDataType]] = None
    coverage: Optional[Coverage] = None
    enrichmentAndLinkage: Optional[EnrichmentAndLinkage] = None
    accessibility: Optional[Accessibility] = None

class ExtractionResponse(BaseModel):
    dataset: Dataset = Field(description="The complete extracted dataset metadata matching the CRUK schema")
    conflicts: List[Conflict] = Field(default_factory=list, description="A list of any conflicts found between the existing data and the incoming document")
