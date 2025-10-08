-- Add currency field to trips table
ALTER TABLE public.trips 
ADD COLUMN currency text DEFAULT 'USD';

-- Add comment to the column
COMMENT ON COLUMN public.trips.currency IS 'Currency code for budget fields (e.g., USD, EUR, ARS)';
