package br.com.finance.FinancePro.financias.Valores.Repository;

import br.com.finance.FinancePro.financias.Valores.Model.ValoresModel;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ValoresRepository extends JpaRepository<ValoresModel, Long> {
}
